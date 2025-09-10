# Оркестратор процесса аудита

import json
from datetime import datetime
from typing import Dict, Any
from loguru import logger

from app.core.utils import normalize_url
from app.core.settings import settings
from app.storage.sqlite import (
    ensure_user_limit,
    can_run,
    increment_counter,
    get_user_sheet_id
)
from app.features.audit.adapters.fetcher import get_content_bundle
from app.features.audit.adapters.llm import analyze_content
from app.features.audit.services.persist import write_or_defer


async def run_audit(user_id: str, url: str) -> Dict[str, Any]:
    """
    Оркестратор полного процесса анализа сайта
    
    Args:
        user_id: ID пользователя
        url: URL для анализа
        
    Returns:
        Словарь с результатом: {"ok": bool, "reason"?: str, "short_summary"?: List, "written_now"?: bool}
    """
    try:
        logger.info(f"Начинаем анализ для пользователя {user_id}, URL: {url}")
        
        # Проверяем и создаем лимиты пользователя
        await ensure_user_limit(user_id, settings.default_user_limit)
        
        # Проверяем может ли пользователь запустить анализ
        if not await can_run(user_id, settings.default_user_limit):
            logger.warning(f"Пользователь {user_id} превысил лимит анализов")
            return {
                "ok": False,
                "reason": "limit"
            }
        
        # Нормализуем URL
        normalized_url = normalize_url(url)
        if not normalized_url:
            logger.error(f"Не удалось нормализовать URL: {url}")
            return {
                "ok": False,
                "reason": "invalid_url"
            }
        
        logger.info(f"Нормализованный URL: {normalized_url}")
        
        # Получаем контент сайта
        logger.info("Загружаем контент сайта...")
        bundle = await get_content_bundle(normalized_url)
        
        if not bundle.get("home_text"):
            logger.error(f"Не удалось получить контент с {normalized_url}")
            return {
                "ok": False,
                "reason": "fetch_failed"
            }
        
        logger.info(f"Контент загружен: {len(bundle['home_text'])} символов главной, pricing: {bool(bundle.get('pricing_text'))}")
        
        # Анализируем контент через LLM
        logger.info("Отправляем на анализ GPT-4o...")
        full_result, short_summary = await analyze_content(
            home_text=bundle["home_text"],
            pricing_text=bundle.get("pricing_text"),
            pricing_url=bundle.get("pricing_url")
        )
        
        logger.info("Анализ GPT-4o завершен")
        
        # Формируем данные для сохранения
        now_iso = datetime.now().isoformat()
        result_data = {
            "full_result": full_result.model_dump(),  # Исправлено: dict() -> model_dump()
            "pricing_url": bundle.get("pricing_url"),
            "timestamp": now_iso,
            "short_summary": short_summary  # Теперь это уже List[str]
        }
        
        # Проверяем есть ли у пользователя таблица
        user_has_sheet = bool(await get_user_sheet_id(user_id))
        
        # Записываем результат (сразу в таблицу или отложенно)
        await write_or_defer(user_id, normalized_url, json.dumps(result_data, ensure_ascii=False))
        
        # Увеличиваем счетчик использования
        await increment_counter(user_id)
        
        logger.info(f"Анализ завершен для пользователя {user_id}, таблица подключена: {user_has_sheet}")
        
        return {
            "ok": True,
            "short_summary": short_summary[:4],  # Убираем .summary_points
            "written_now": user_has_sheet,
        }
        
    except Exception as e:
        logger.error(f"Ошибка в процессе анализа для {user_id}: {e}")
        return {
            "ok": False,
            "reason": "internal_error",
            "error": str(e)
        }


async def run_audit_service(user_id: str, url: str, chat_id: int, bot) -> None:
    """
    Сервисная функция для запуска анализа из Telegram бота
    
    Args:
        user_id: ID пользователя
        url: URL для анализа  
        chat_id: ID чата для отправки результата
        bot: Экземпляр Telegram бота
    """
    try:
        # Запускаем анализ
        result = await run_audit(user_id, url)
        
        # Обрабатываем результат и отправляем ответ пользователю
        await handle_audit_result(result, chat_id, bot)
        
    except Exception as e:
        logger.error(f"Ошибка в сервисной функции анализа: {e}")
        
        # Отправляем сообщение об ошибке
        from app.telegram import texts
        try:
            await bot.send_message(chat_id, texts.ERROR_GENERIC)
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}")


async def handle_audit_result(result: Dict[str, Any], chat_id: int, bot) -> None:
    """
    Обработка результата анализа и отправка ответа пользователю
    
    Args:
        result: Результат анализа из run_audit
        chat_id: ID чата для отправки
        bot: Экземпляр Telegram бота
    """
    from app.telegram import texts, keyboards
    
    try:
        if not result["ok"]:
            # Обрабатываем ошибки
            if result.get("reason") == "limit":
                await bot.send_message(
                    chat_id, 
                    "Лимит анализов исчерпан. Обратитесь к администратору."
                )
            else:
                await bot.send_message(chat_id, texts.ERROR_GENERIC)
            return
        
        # Формируем сообщение с результатом
        short_summary = result["short_summary"]
        written_now = result["written_now"]
        
        if written_now:
            # Результат записан в таблицу пользователя
            summary_text = texts.RESULT_WITH_SHEET_PREFIX
            for item in short_summary:
                summary_text += texts.RESULT_WITH_SHEET_BULLET.format(item=item)
            
            await bot.send_message(
                chat_id,
                summary_text,
                reply_markup=keyboards.after_result_with_sheet_kb()
            )
        else:
            # Результат сохранен отложенно
            await bot.send_message(
                chat_id,
                texts.RESULT_NO_SHEET,
                reply_markup=keyboards.after_result_no_sheet_kb()
            )
        
        logger.info(f"Результат анализа отправлен в чат {chat_id}")
        
    except Exception as e:
        logger.error(f"Ошибка отправки результата анализа: {e}")
        try:
            await bot.send_message(chat_id, texts.ERROR_GENERIC)
        except:
            pass