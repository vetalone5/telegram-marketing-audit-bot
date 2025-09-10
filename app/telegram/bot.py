import asyncio
import fcntl
import os
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler
)
from telegram.error import Conflict
from telegram import Update
from loguru import logger

from app.core.settings import settings
from app.core.logging import setup_logging
from app.telegram.handlers import (
    start_command,
    button_callback_handler,
    url_message_handler,
    sheet_url_message_handler,
    set_limit_command,
    error_handler
)

# Состояния для ConversationHandler
WAITING_FOR_URL, WAITING_FOR_SHEET_URL = range(2)

# Файл для lock защиты от множественных запусков
LOCK_FILE = "/tmp/marketgaze_bot.lock"


class BotLock:
    """Файловый lock для предотвращения множественных запусков"""
    
    def __init__(self, lock_file: str):
        self.lock_file = lock_file
        self.lock_fd = None
    
    def acquire(self) -> bool:
        """Захватить lock. Возвращает True если успешно"""
        try:
            self.lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd.write(str(os.getpid()))
            self.lock_fd.flush()
            return True
        except (IOError, OSError):
            if self.lock_fd:
                self.lock_fd.close()
            return False
    
    def release(self):
        """Освободить lock"""
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
                self.lock_fd.close()
                os.unlink(self.lock_file)
            except (IOError, OSError):
                pass


def create_application() -> Application:
    """Создание и настройка Telegram Application"""
    
    # Создаем приложение
    application = Application.builder().token(settings.telegram_token).build()
    
    # Обработчик команды /start
    application.add_handler(CommandHandler("start", start_command))
    
    # Обработчик админ-команды /set_limit
    application.add_handler(CommandHandler("set_limit", set_limit_command))
    
    # ConversationHandler для состояний
    # ИСПРАВЛЕНИЕ: per_message=False для совместимости с MessageHandler
    conv_handler = ConversationHandler(
        entry_points=[
            # Добавляем callback кнопки как точки входа в диалог
            CallbackQueryHandler(button_callback_handler)
        ],
        states={
            WAITING_FOR_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, url_message_handler)
            ],
            WAITING_FOR_SHEET_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sheet_url_message_handler)
            ],
        },
        fallbacks=[CommandHandler("start", start_command)],
        per_message=False,  # ИСПРАВЛЕНО: False для совместимости с MessageHandler
        per_chat=True,
        per_user=True,
        allow_reentry=True  # Добавляем для возможности повторного входа
    )
    
    application.add_handler(conv_handler)
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    logger.info("Telegram Application настроено")
    return application


async def main():
    """Главная функция запуска бота"""
    bot_lock = None
    
    try:
        # Настраиваем логирование
        setup_logging()
        logger.info("Запуск Telegram бота...")
        
        # Защита от множественных запусков
        bot_lock = BotLock(LOCK_FILE)
        if not bot_lock.acquire():
            logger.error("Обнаружен другой экземпляр бота. Завершение.")
            exit(1)
        
        logger.info("Lock захвачен, продолжаем запуск")
        
        # Создаем приложение
        application = create_application()
        
        # Инициализируем приложение
        await application.initialize()
        
        # Удаляем webhook перед запуском polling
        logger.info("Удаляю webhook...")
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook удалён")
        
        # Запускаем updater
        await application.start()
        
        # Начинаем polling с правильными параметрами
        logger.info("Старт polling...")
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        logger.info("Бот запущен в режиме polling")
        
        # Держим бота запущенным
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки")
        
        # Останавливаем бота
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        
    except Conflict as e:
        logger.error("Обнаружен другой экземпляр бота (или активный webhook). Завершение.")
        exit(1)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise
    finally:
        # Освобождаем lock при любом завершении
        if bot_lock:
            bot_lock.release()
            logger.info("Lock освобожден")


if __name__ == "__main__":
    try:
        # Используем простой синхронный запуск
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        # Не поднимаем исключение, просто завершаемся