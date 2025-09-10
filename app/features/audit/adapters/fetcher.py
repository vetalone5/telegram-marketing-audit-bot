import httpx
import re
from typing import Optional, Dict, List
from urllib.parse import urljoin, urlparse
from loguru import logger

from app.core.utils import normalize_url
from app.core.retry import retry_on_network_error, retry_on_api_error
from app.core.settings import settings
from app.features.audit.adapters.cleaner import clean_html

# Флаг для контроля использования web tools (синхронизирован с llm.py)
USE_WEB_TOOLS = False  # По умолчанию отключен для стабильности


@retry_on_network_error
async def http_fetch(url: str) -> str:
    """
    Загрузка страницы через httpx
    
    Args:
        url: URL для загрузки
        
    Returns:
        HTML содержимое страницы
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            
            logger.debug(f"HTTP загрузка {url}: {response.status_code}, {len(response.text)} символов")
            return response.text
            
    except Exception as e:
        logger.error(f"Ошибка HTTP загрузки {url}: {e}")
        raise


def find_pricing_link(home_html: str, base_url: str) -> Optional[str]:
    """
    Поиск ссылки на страницу с ценами
    
    Args:
        home_html: HTML содержимое главной страницы
        base_url: Базовый URL для формирования абсолютных ссылок
        
    Returns:
        Абсолютный URL страницы с ценами или None
    """
    try:
        # Ключевые слова для поиска ценовых страниц
        pricing_keywords = [
            "цены", "цена", "тариф", "тарифы", "стоимость", "прайс",
            "pricing", "price", "prices", "tariff", "cost", "payment", "план"
        ]
        
        # Паттерн для поиска ссылок
        link_pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>'
        
        matches = re.findall(link_pattern, home_html, re.IGNORECASE | re.DOTALL)
        
        for href, link_text in matches:
            # Проверяем текст ссылки и href на наличие ключевых слов
            combined_text = f"{href} {link_text}".lower()
            
            for keyword in pricing_keywords:
                if keyword in combined_text:
                    # Формируем абсолютный URL
                    absolute_url = urljoin(base_url, href)
                    
                    # Проверяем что это не якорная ссылка и не внешний сайт
                    parsed_base = urlparse(base_url)
                    parsed_link = urlparse(absolute_url)
                    
                    if (parsed_link.netloc == parsed_base.netloc and 
                        not href.startswith('#') and 
                        not href.startswith('mailto:') and
                        not href.startswith('tel:')):
                        
                        logger.info(f"Найдена ссылка на цены: {absolute_url} (ключевое слово: {keyword})")
                        return absolute_url
        
        logger.debug(f"Ссылка на цены не найдена на {base_url}")
        return None
        
    except Exception as e:
        logger.error(f"Ошибка поиска ссылки на цены: {e}")
        return None


async def get_content_bundle(url: str) -> Dict[str, any]:
    """
    Получение полного контента сайта (главная + цены)
    
    Args:
        url: URL сайта для анализа
        
    Returns:
        Словарь с контентом: {home_text, pricing_text?, pricing_url?, requires_js?}
    """
    try:
        # Нормализуем URL
        normalized_url = normalize_url(url)
        if not normalized_url:
            raise ValueError(f"Не удалось нормализовать URL: {url}")
        
        logger.info(f"Начинаем загрузку контента для {normalized_url}")
        
        # Проверяем флаг USE_WEB_TOOLS
        if USE_WEB_TOOLS:
            logger.info("Используем web tools для загрузки контента")
            try:
                # Импортируем run_with_tools из llm.py для правильного tool-цикла
                from app.features.audit.adapters.llm import run_with_tools
                
                # Формируем сообщения для tool-цикла
                messages = [
                    {
                        "role": "system",
                        "content": "Ты помощник для загрузки контента веб-страниц. Используй fetch_url tool для получения содержимого страниц. Верни JSON с ключами: home_text, pricing_text (если есть), pricing_url (если есть)."
                    },
                    {
                        "role": "user", 
                        "content": f"Загрузи содержимое страницы {normalized_url}. Если найдешь ссылки на цены/тарифы/pricing, загрузи и их тоже."
                    }
                ]
                
                # Выполняем tool-цикл
                result_text = await run_with_tools(messages)
                
                # Пытаемся извлечь JSON из ответа
                import json
                import re
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    result_data = json.loads(json_match.group(0))
                    logger.info(f"Web tools успешно загрузили контент для {normalized_url}")
                    return result_data
                else:
                    # Если JSON не найден, fallback на простой ответ
                    return {"home_text": result_text[:8000]}
                    
            except Exception as web_tool_error:
                logger.warning(f"Web tools не сработали для {normalized_url}: {web_tool_error}")
                logger.info("Переходим на HTTP fallback")
        else:
            logger.info("Web tools отключены, используем HTTP fallback")
        
        # HTTP fallback - надежный метод
        logger.info(f"Загружаем контент через HTTP для {normalized_url}")
        
        # Загружаем главную страницу
        home_html = await http_fetch(normalized_url)
        home_text = clean_html(home_html)
        
        if not home_text or len(home_text.strip()) < 50:
            logger.error(f"Получен пустой или слишком короткий контент с {normalized_url}")
            return {"home_text": "", "requires_js": True}
        
        result = {
            "home_text": home_text,
            "requires_js": len(home_text.strip()) < 500  # Подозреваем JS если текста мало
        }
        
        # Ищем и загружаем страницу с ценами
        pricing_url = find_pricing_link(home_html, normalized_url)
        if pricing_url:
            try:
                logger.info(f"Найдена ссылка на цены: {pricing_url}")
                pricing_html = await http_fetch(pricing_url)
                pricing_text = clean_html(pricing_html)
                
                if pricing_text and len(pricing_text.strip()) > 50:
                    result["pricing_url"] = pricing_url
                    result["pricing_text"] = pricing_text
                    logger.info(f"Загружена страница с ценами: {pricing_url}")
                else:
                    logger.warning(f"Страница с ценами пуста или слишком короткая: {pricing_url}")
                    
            except Exception as pricing_error:
                logger.warning(f"Не удалось загрузить pricing {pricing_url}: {pricing_error}")
        else:
            logger.debug(f"Ссылка на цены не найдена для {normalized_url}")
        
        logger.info(f"HTTP fallback завершен для {normalized_url}: {len(result['home_text'])} символов главной")
        return result
    
    except Exception as e:
        logger.error(f"Критическая ошибка загрузки контента {url}: {e}")
        raise