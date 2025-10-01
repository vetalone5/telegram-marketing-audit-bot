from typing import Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
from loguru import logger
from app.features.audit.adapters.cleaner import clean_html

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
    logger.info("Playwright модуль загружен успешно")
except ImportError as e:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning(f"Playwright не доступен: {e}")


async def get_content_bundle_playwright(url: str) -> Dict[str, str]:
    """
    Версия get_content_bundle с поддержкой JS-рендеринга через Playwright
    
    Args:
        url: URL для анализа
        
    Returns:
        Dict с ключами: home_text, pricing_text, pricing_url
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("Playwright не установлен")
        
    try:
        logger.info(f"Запуск Playwright анализа для: {url}")
        
        async with async_playwright() as p:
            # Запускаем headless браузер с оптимизациями
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            
            # Создаем контекст с реалистичными настройками
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale='ru-RU'
            )
            
            page = await context.new_page()
            
            # Блокируем ненужные ресурсы для ускорения
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,mp4,mp3,webm,pdf,zip,rar}", 
                            lambda route: route.abort())
            
            # Блокируем аналитику и рекламу
            await page.route("**/analytics.js", lambda route: route.abort())
            await page.route("**/gtag.js", lambda route: route.abort())
            await page.route("**/facebook.com/**", lambda route: route.abort())
            await page.route("**/google-analytics.com/**", lambda route: route.abort())
            await page.route("**/googletagmanager.com/**", lambda route: route.abort())
            
            # Загружаем главную страницу
            logger.debug(f"Загружаем главную страницу: {url}")
            await page.goto(url, wait_until="networkidle", timeout=20000)
            
            # Ждем рендеринга JavaScript
            await page.wait_for_timeout(3000)
            
            # Получаем текст после JS рендеринга
            home_text = await page.inner_text("body")
            logger.info(f"Получено {len(home_text)} символов с главной страницы")
            
            # Ищем страницу с ценами
            pricing_url, pricing_text = await find_pricing_page_playwright(page, url)
            
            await browser.close()
            
            return {
                "home_text": clean_html(home_text),
                "pricing_text": pricing_text or "",
                "pricing_url": pricing_url or ""
            }
            
    except Exception as e:
        logger.error(f"Ошибка Playwright для {url}: {e}")
        raise


async def find_pricing_page_playwright(page, base_url: str) -> Tuple[Optional[str], str]:
    """
    Умный поиск страницы с ценами через браузер
    
    Args:
        page: Playwright страница
        base_url: Базовый URL сайта
        
    Returns:
        Tuple (pricing_url, pricing_text)
    """
    try:
        logger.debug("Ищем страницу с ценами...")
        
        # Расширенные паттерны поиска ссылок на цены
        pricing_selectors = [
            # Английские варианты в href
            'a[href*="pricing" i]',
            'a[href*="price" i]', 
            'a[href*="plans" i]',
            'a[href*="tariff" i]',
            'a[href*="cost" i]',
            
            # Русские варианты в href
            'a[href*="тариф" i]',
            'a[href*="стоимость" i]',
            'a[href*="цена" i]',
            'a[href*="цены" i]',
            'a[href*="прайс" i]',
            
            # По тексту ссылки (английский)
            'a:has-text("Pricing")',
            'a:has-text("Prices")',
            'a:has-text("Plans")',
            'a:has-text("Cost")',
            'a:has-text("Tariffs")',
            'a:has-text("Subscribe")',
            
            # По тексту ссылки (русский)
            'a:has-text("Цены")',
            'a:has-text("Тарифы")',
            'a:has-text("Стоимость")',
            'a:has-text("Расценки")',
            'a:has-text("Прайс")',
            'a:has-text("Подписка")',
            'a:has-text("Тарифный план")',
            
            # Кнопки с ценами
            'button:has-text("Цены")',
            'button:has-text("Тарифы")',
            'button:has-text("Pricing")',
            'button:has-text("Plans")',
            
            # Навигационные элементы
            'nav a:has-text("Цены")',
            'nav a:has-text("Тарифы")',
            'nav a:has-text("Pricing")',
            '.menu a:has-text("Цены")',
            '.navigation a:has-text("Pricing")',
            'header a:has-text("Цены")'
        ]
        
        found_links = []
        
        # Собираем все потенциальные ссылки
        for selector in pricing_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    href = await element.get_attribute("href")
                    text = await element.inner_text()
                    
                    if href:
                        full_url = urljoin(base_url, href)
                        found_links.append({
                            'url': full_url,
                            'text': text.strip(),
                            'selector': selector
                        })
                        logger.debug(f"Найдена ссылка: {text.strip()} -> {full_url}")
                        
            except Exception as e:
                logger.debug(f"Ошибка поиска по селектору {selector}: {e}")
                continue
        
        # Убираем дубликаты
        unique_links = []
        seen_urls = set()
        for link in found_links:
            if link['url'] not in seen_urls:
                unique_links.append(link)
                seen_urls.add(link['url'])
        
        logger.info(f"Найдено {len(unique_links)} уникальных ссылок на цены")
        
        # Приоритизируем ссылки (сначала самые релевантные)
        priority_keywords = ['pricing', 'цены', 'тариф', 'price', 'plans', 'стоимость']
        
        def get_priority(link):
            url_lower = link['url'].lower()
            text_lower = link['text'].lower()
            for i, keyword in enumerate(priority_keywords):
                if keyword in url_lower or keyword in text_lower:
                    return i
            return len(priority_keywords)
        
        unique_links.sort(key=get_priority)
        
        # Пробуем загрузить первые 3 наиболее релевантные ссылки
        for link in unique_links[:3]:
            try:
                pricing_url = link['url']
                
                # Проверяем что это не внешняя ссылка
                parsed_base = urlparse(base_url)
                parsed_pricing = urlparse(pricing_url)
                
                if parsed_pricing.netloc != parsed_base.netloc:
                    logger.debug(f"Пропускаем внешнюю ссылку: {pricing_url}")
                    continue
                
                logger.info(f"Переходим на страницу цен: {pricing_url}")
                
                # Переходим на страницу цен
                await page.goto(pricing_url, wait_until="networkidle", timeout=15000)
                await page.wait_for_timeout(2000)
                
                # Получаем контент
                pricing_text = await page.inner_text("body")
                
                # Проверяем что страница содержит информацию о ценах
                if len(pricing_text) > 500:  # Минимальный размер контента
                    logger.info(f"Успешно загружена страница цен: {pricing_url} ({len(pricing_text)} символов)")
                    return pricing_url, clean_html(pricing_text)
                else:
                    logger.debug(f"Страница {pricing_url} содержит мало контента ({len(pricing_text)} символов)")
                    
            except Exception as e:
                logger.debug(f"Ошибка загрузки страницы цен {link['url']}: {e}")
                continue
        
        logger.info("Страница с ценами не найдена или недоступна")
        return None, ""
        
    except Exception as e:
        logger.error(f"Ошибка поиска страницы цен: {e}")
        return None, ""