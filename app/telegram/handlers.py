import re
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger

from app.core.settings import settings
from app.storage.sqlite import get_user_sheet_id, set_user_sheet_id, set_limit
from app.features.audit.services.run_audit import run_audit_service
from app.features.audit.services.persist import flush_pending_to_user_sheet
from app.features.audit.adapters.sheets import get_service_email
from app.telegram import texts, keyboards

# Состояния для ConversationHandler
WAITING_FOR_URL, WAITING_FOR_SHEET_URL = range(2)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start"""
    try:
        user_id = str(update.effective_user.id)
        logger.info(f"Команда /start от пользователя {user_id}")
        
        # Проверяем есть ли у пользователя подключенная таблица
        sheet_id = await get_user_sheet_id(user_id)
        
        if sheet_id:
            # У пользователя есть таблица
            await update.message.reply_text(
                texts.WELCOME_WITH_SHEET,
                reply_markup=keyboards.main_kb(),
                parse_mode='HTML'
            )
        else:
            # Таблица не подключена
            await update.message.reply_text(
                texts.WELCOME_NO_SHEET,
                reply_markup=keyboards.single_start_kb(),
                parse_mode='HTML'
            )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка в start_command: {e}")
        await update.message.reply_text(texts.ERROR_GENERIC, parse_mode='HTML')
        return ConversationHandler.END


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик нажатий на inline кнопки"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = str(query.from_user.id)
        data = query.data
        
        logger.info(f"Callback {data} от пользователя {user_id}")
        
        if data == "start_analysis" or data == "new_analysis":
            # Начать новый анализ
            logger.debug(f"Переходим в состояние WAITING_FOR_URL для {user_id}")
            await query.edit_message_text(texts.ASK_FOR_URL, parse_mode='HTML')
            return WAITING_FOR_URL
            
        elif data == "connect_sheet":
            # Подключить таблицу
            logger.debug(f"Переходим в состояние WAITING_FOR_SHEET_URL для {user_id}")
            try:
                service_email = await get_service_email()
                instructions = texts.CONNECT_INSTRUCTIONS.format(service_email=service_email)
                await query.edit_message_text(instructions, parse_mode='HTML')
                return WAITING_FOR_SHEET_URL
            except Exception as e:
                logger.error(f"Ошибка получения service_email: {e}")
                await query.edit_message_text(texts.ERROR_GENERIC, parse_mode='HTML')
                return ConversationHandler.END
                
        elif data == "open_sheet":
            # Открыть таблицу
            sheet_id = await get_user_sheet_id(user_id)
            if sheet_id:
                sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
                await query.edit_message_text(
                    f"Твоя таблица: {sheet_url}",
                    reply_markup=keyboards.main_kb(),
                    parse_mode='HTML'
                )
            else:
                # Открыть резервную таблицу
                default_sheet_url = f"https://docs.google.com/spreadsheets/d/{settings.google_sheets_id}"
                await query.edit_message_text(
                    f"Резервная таблица: {default_sheet_url}",
                    reply_markup=keyboards.main_kb(),
                    parse_mode='HTML'
                )
            return ConversationHandler.END
        
        logger.debug(f"Завершаем диалог для {user_id}")
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка в button_callback_handler: {e}")
        await query.edit_message_text(texts.ERROR_GENERIC, parse_mode='HTML')
        return ConversationHandler.END


async def url_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик URL для анализа"""
    try:
        user_id = str(update.effective_user.id)
        url = update.message.text.strip()
        
        logger.info(f"Получен URL для анализа от {user_id}: {url}")
        logger.debug(f"Завершаем состояние WAITING_FOR_URL для {user_id}")
        
        # Отправляем сообщение о начале анализа
        await update.message.reply_text(texts.ANALYSIS_STARTED, parse_mode='HTML')
        
        # Запускаем анализ в фоновом режиме
        context.application.create_task(
            run_audit_service(user_id, url, update.effective_chat.id, context.bot)
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка в url_message_handler: {e}")
        await update.message.reply_text(texts.ERROR_GENERIC, parse_mode='HTML')
        return ConversationHandler.END


async def sheet_url_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик URL Google Sheets для подключения"""
    try:
        user_id = str(update.effective_user.id)
        sheet_url = update.message.text.strip()
        
        logger.info(f"Получен URL таблицы от {user_id}: {sheet_url}")
        logger.debug(f"Завершаем состояние WAITING_FOR_SHEET_URL для {user_id}")
        
        # Извлекаем sheet_id из URL
        sheet_id = extract_sheet_id(sheet_url)
        if not sheet_id:
            await update.message.reply_text(
                "Неверный формат ссылки на Google Таблицу. Попробуйте еще раз.",
                parse_mode='HTML'
            )
            return WAITING_FOR_SHEET_URL
        
        # Сохраняем sheet_id в БД
        await set_user_sheet_id(user_id, sheet_id)
        
        # Переносим отложенные результаты
        count = await flush_pending_to_user_sheet(user_id)
        
        # Отправляем подтверждение
        message = texts.CONNECTED_AND_FLUSHED.format(count=count)
        await update.message.reply_text(
            message,
            reply_markup=keyboards.after_result_with_sheet_kb(),
            parse_mode='HTML'
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка в sheet_url_message_handler: {e}")
        await update.message.reply_text(texts.ERROR_GENERIC, parse_mode='HTML')
        return ConversationHandler.END


def extract_sheet_id(url: str) -> str:
    """Извлечение sheet_id из URL Google Sheets"""
    try:
        # Паттерн для извлечения ID из Google Sheets URL
        patterns = [
            r"/spreadsheets/d/([a-zA-Z0-9-_]+)",
            r"id=([a-zA-Z0-9-_]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return ""
        
    except Exception as e:
        logger.error(f"Ошибка извлечения sheet_id из URL {url}: {e}")
        return ""


async def set_limit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Админ-команда для установки лимита пользователя: /set_limit <user_id> <limit>"""
    try:
        admin_user_id = update.effective_user.id
        
        # Проверяем что пользователь администратор
        if not settings.is_admin(admin_user_id):
            await update.message.reply_text("У вас нет прав для выполнения этой команды.")
            return ConversationHandler.END
        
        # Проверяем аргументы команды
        if not context.args or len(context.args) != 2:
            await update.message.reply_text(
                "Использование: /set_limit <user_id> <лимит>\n"
                "Пример: /set_limit 123456789 50",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        try:
            target_user_id = context.args[0]
            new_limit = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Лимит должен быть числом.", parse_mode='HTML')
            return ConversationHandler.END
        
        if new_limit < 0:
            await update.message.reply_text("Лимит не может быть отрицательным.", parse_mode='HTML')
            return ConversationHandler.END
        
        # Устанавливаем лимит
        await set_limit(target_user_id, new_limit)
        
        await update.message.reply_text(
            f"Лимит для пользователя {target_user_id} установлен: {new_limit}",
            parse_mode='HTML'
        )
        
        logger.info(f"Админ {admin_user_id} установил лимит {new_limit} для пользователя {target_user_id}")
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка в set_limit_command: {e}")
        await update.message.reply_text(texts.ERROR_GENERIC, parse_mode='HTML')
        return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик ошибок"""
    logger.error(f"Глобальная ошибка: {context.error}")
    
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(texts.ERROR_GENERIC, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")