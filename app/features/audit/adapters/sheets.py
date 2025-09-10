import gspread
from google.oauth2.service_account import Credentials
from typing import Dict, List, Optional
from loguru import logger

from app.core.settings import settings
from app.core.retry import retry_on_api_error

# Список заголовков колонок в нужном порядке (РУССКИЕ названия)
SHEET_HEADERS = [
    "Дата и время анализа",
    "ID пользователя", 
    "Ссылка",
    "Страница с ценами",  # Добавляем URL страницы с ценами
    "Оффер (первый экран)",
    "CTA (первый экран)",
    "УТП (по формуле)",
    "Продукт / услуги (кратко)",
    "Программа обучения",
    "Все CTA (текст + контекст)",
    "Выгоды",
    "Боли ЦА",
    "Цены и тарифы (с источником)",
    "Рассрочка / Оплата позже",
    "Акции (условия/сроки)",
    "Бонусы / Подарки",
    "Гарантии",
    "Факторы доверия",
    "Лид-магниты / Квизы",
    "Контакты и соцсети",
    "Онлайн-чат (наличие/тип/расположение)",
    "Формы заявки (поля/кнопки)",
    "Структура главной (сверху вниз)",
    "FAQ (10–15 ключевых)",
    "Маркетинговые выводы",
    "Гипотезы роста (SMART)",
    "Краткая сводка (3–4 пункта)",
    "Заметки (служебно)"
]


def get_gspread_client() -> gspread.Client:
    """Создание авторизованного клиента Google Sheets"""
    try:
        # Определяем области доступа
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Создаем credentials из service account файла
        credentials = Credentials.from_service_account_file(
            settings.google_service_json_path,
            scopes=scopes
        )
        
        # Создаем клиент
        client = gspread.authorize(credentials)
        
        logger.debug("Google Sheets клиент создан успешно")
        return client
        
    except Exception as e:
        logger.error(f"Ошибка создания Google Sheets клиента: {e}")
        raise


async def get_service_email() -> str:
    """Получение email сервисного аккаунта для предоставления доступа"""
    try:
        credentials = Credentials.from_service_account_file(
            settings.google_service_json_path
        )
        
        service_email = credentials.service_account_email
        logger.debug(f"Service account email: {service_email}")
        return service_email
        
    except Exception as e:
        logger.error(f"Ошибка получения service account email: {e}")
        raise


@retry_on_api_error
async def ensure_headers(sheet_id: str) -> None:
    """
    Проверка и создание заголовков в Google Sheets
    
    Args:
        sheet_id: ID Google таблицы
    """
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(sheet_id)
        
        # Работаем с первым листом
        worksheet = sheet.sheet1
        
        # Проверяем существующие заголовки
        try:
            existing_headers = worksheet.row_values(1)
            
            # Если заголовки уже есть и совпадают, ничего не делаем
            if existing_headers == SHEET_HEADERS:
                logger.debug(f"Заголовки в таблице {sheet_id} уже корректные")
                return
                
            # Если заголовки есть но не совпадают, логируем предупреждение
            if existing_headers:
                logger.warning(f"Заголовки в таблице {sheet_id} не совпадают с ожидаемыми")
                return
                
        except Exception:
            # Если не удалось получить заголовки, значит таблица пустая
            pass
        
        # Создаем заголовки
        worksheet.insert_row(SHEET_HEADERS, index=1)
        
        # Форматируем заголовки (жирный шрифт)
        try:
            worksheet.format('1:1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
        except Exception as format_error:
            logger.warning(f"Не удалось отформатировать заголовки: {format_error}")
        
        logger.info(f"Заголовки созданы в таблице {sheet_id}")
        
    except Exception as e:
        logger.error(f"Ошибка создания заголовков в таблице {sheet_id}: {e}")
        raise


@retry_on_api_error
async def write_row(sheet_id: str, row_data: List[str]) -> None:
    """
    Запись строки в конец Google Sheets
    
    Args:
        sheet_id: ID Google таблицы
        row_data: Список значений для записи
    """
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.sheet1
        
        # Убеждаемся что заголовки есть
        await ensure_headers(sheet_id)
        
        # Добавляем строку в конец
        worksheet.append_row(row_data)
        
        logger.info(f"Строка записана в таблицу {sheet_id}: {len(row_data)} колонок")
        
    except Exception as e:
        logger.error(f"Ошибка записи строки в таблицу {sheet_id}: {e}")
        raise


async def test_sheet_access(sheet_id: str) -> bool:
    """
    Тест доступа к Google таблице
    
    Args:
        sheet_id: ID Google таблицы
        
    Returns:
        True если доступ есть
    """
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(sheet_id)
        
        # Пробуем получить название таблицы
        title = sheet.title
        logger.info(f"Доступ к таблице '{title}' подтвержден")
        return True
        
    except Exception as e:
        logger.error(f"Нет доступа к таблице {sheet_id}: {e}")
        return False


async def get_sheet_url(sheet_id: str) -> str:
    """Формирование URL Google таблицы"""
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"