# Сохранение и управление результатами аудита

import json
from typing import Dict, List, Optional
from loguru import logger

from app.storage.sqlite import (
    get_user_sheet_id,
    save_pending_result,
    fetch_unwritten_results,
    mark_written
)
from app.features.audit.adapters.sheets import ensure_headers, write_row
from app.features.audit.schemas.models import RowForSheet


async def write_or_defer(user_id: str, url: str, result_json: str) -> None:
    """
    Записать результат в таблицу пользователя или сохранить отложенно
    
    Args:
        user_id: ID пользователя
        url: URL анализируемого сайта
        result_json: JSON строка с результатами анализа
    """
    try:
        # Проверяем есть ли у пользователя подключенная таблица
        user_sheet = await get_user_sheet_id(user_id)
        
        if user_sheet:
            # У пользователя есть таблица - записываем сразу
            logger.info(f"Записываем результат сразу в таблицу {user_sheet} для пользователя {user_id}")
            
            # Убеждаемся что заголовки есть
            await ensure_headers(user_sheet)
            
            # Конвертируем JSON в строку для таблицы
            row_data = convert_json_to_row(result_json, user_id, url)
            
            # Записываем в таблицу
            await write_row(user_sheet, row_data)
            
            logger.info(f"Результат записан в таблицу {user_sheet}")
            
        else:
            # Таблица не подключена - сохраняем отложенно
            logger.info(f"Сохраняем результат отложенно для пользователя {user_id}")
            
            result_id = await save_pending_result(user_id, url, result_json)
            
            logger.info(f"Результат сохранен отложенно с ID {result_id}")
    
    except Exception as e:
        logger.error(f"Ошибка записи/отложения результата для {user_id}: {e}")
        raise


async def flush_pending_to_user_sheet(user_id: str) -> int:
    """
    Перенос всех отложенных результатов в таблицу пользователя
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Количество перенесенных результатов
    """
    try:
        # Проверяем есть ли у пользователя таблица
        user_sheet = await get_user_sheet_id(user_id)
        if not user_sheet:
            logger.debug(f"У пользователя {user_id} нет подключенной таблицы")
            return 0
        
        # Получаем отложенные результаты
        results = await fetch_unwritten_results(user_id)
        if not results:
            logger.debug(f"У пользователя {user_id} нет отложенных результатов")
            return 0
        
        logger.info(f"Начинаем перенос {len(results)} результатов в таблицу {user_sheet}")
        
        # Убеждаемся что заголовки есть
        await ensure_headers(user_sheet)
        
        # Переносим каждый результат
        counter = 0
        for result in results:
            try:
                # Конвертируем JSON в строку для таблицы
                row_data = convert_json_to_row(
                    result['result_json'], 
                    user_id, 
                    result['url']
                )
                
                # Записываем в таблицу
                await write_row(user_sheet, row_data)
                
                # Отмечаем как записанный
                await mark_written(result['id'])
                
                counter += 1
                logger.debug(f"Результат {result['id']} перенесен успешно")
                
            except Exception as row_error:
                logger.error(f"Ошибка переноса результата {result['id']}: {row_error}")
                # Продолжаем с другими результатами
                continue
        
        logger.info(f"Перенесено {counter} из {len(results)} результатов в таблицу {user_sheet}")
        return counter
        
    except Exception as e:
        logger.error(f"Ошибка переноса отложенных результатов для {user_id}: {e}")
        return 0


def convert_json_to_row(result_json: str, user_id: str, url: str) -> List[str]:
    """
    Конвертация JSON результата в строку для Google Sheets
    
    Args:
        result_json: JSON строка с результатами анализа
        user_id: ID пользователя
        url: URL анализируемого сайта
        
    Returns:
        Список строк для записи в таблицу
    """
    try:
        # Парсим JSON
        data = json.loads(result_json)
        
        # Извлекаем данные результата и метаданные
        full_result_data = data.get('full_result', {})
        pricing_url = data.get('pricing_url', '')
        
        # Создаем объект RowForSheet с пустыми значениями по умолчанию
        row_data = RowForSheet(
            timestamp="",  # Будет заполнено автоматически
            user_id=user_id,
            analyzed_url=url,
            pricing_url=pricing_url,
            **{field: full_result_data.get(field, '') for field in [
                'offer_first_screen', 'cta_first_screen', 'utp_formula',
                'product_services', 'education_program', 'all_cta',
                'benefits', 'target_audience_pains', 'prices_tariffs',
                'installment_payment', 'promotions', 'bonuses_gifts',
                'guarantees', 'trust_factors', 'lead_magnets',
                'contacts_social', 'online_chat', 'application_forms',
                'main_structure', 'faq', 'marketing_insights',
                'growth_hypotheses', 'brief_summary', 'notes'
            ]}
        )
        
        # Конвертируем в список для записи в таблицу
        return row_data.to_sheet_row()
        
    except Exception as e:
        logger.error(f"Ошибка конвертации JSON в строку таблицы: {e}")
        logger.error(f"JSON содержимое: {result_json[:500]}...")
        
        # Возвращаем базовую строку с ошибкой
        from datetime import datetime
        return [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id,
            url,
            "",  # pricing_url
            f"Ошибка обработки: {str(e)}"  # В поле оффера
        ] + [""] * 23  # Остальные поля пустые