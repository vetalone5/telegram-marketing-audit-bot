"""
Playwright модуль для обработки динамических веб-страниц.
Обеспечивает полную поддержку JavaScript и SPA приложений.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from app.core.settings import settings


logger = logging.getLogger(__name__)


@dataclass
class PlaywrightConfig:
    """Конфигурация для Playwright"""
    headless: bool = True
    timeout: int = 30000
    wait_for_load_state: str = "networkidle"
    viewport: Dict[str, int] = None
    user_agent: str = None
    accept_downloads: bool = False
    ignore_https_errors: bool = True
    
    def __post_init__(self):
        if self.viewport is None:
            self.viewport = {"width": 1920, "height": 1080}
        if self.user_agent is None:
            self.user_agent = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )


class PlaywrightFetcher:
    """Fetcher для работы с динамическими веб-страницами через Playwright"""
    
    def __init__(self, config: Optional[PlaywrightConfig] = None):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright не установлен. Установите: pip install playwright && playwright install chromium"
            )
        
        self.config = config or PlaywrightConfig()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        
    async def start(self):
        """Запуск Playwright браузера"""
        try:
            self.playwright = await async_playwright().start()
            
            # Запускаем браузер с оптимальными настройками
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--disable-gpu'
                ]
            )
            
            # Создаем контекст с настройками
            self.context = await self.browser.new_context(
                viewport=self.config.viewport,
                user_agent=self.config.user_agent,
                accept_downloads=self.config.accept_downloads,
                ignore_https_errors=self.config.ignore_https_errors
            )
            
            logger.info("Playwright браузер успешно запущен")
            
        except Exception as e:
            logger.error(f"Ошибка запуска Playwright: {e}")
            raise
            
    async def close(self):
        """Закрытие браузера и освобождение ресурсов"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
            logger.info("Playwright браузер закрыт")
        except Exception as e:
            logger.error(f"Ошибка закрытия Playwright: {e}")
            
    async def fetch_page_content(self, url: str, wait_for_selector: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение контента страницы с полной поддержкой JavaScript
        
        Args:
            url: URL страницы
            wait_for_selector: CSS селектор для ожидания загрузки
            
        Returns:
            Словарь с данными страницы
        """
        if not self.context:
            raise RuntimeError("Playwright не инициализирован. Вызовите start() или используйте async with")
            
        page = None
        try:
            page = await self.context.new_page()
            
            # Устанавливаем таймауты
            page.set_default_timeout(self.config.timeout)
            page.set_default_navigation_timeout(self.config.timeout)
            
            # Переходим на страницу
            logger.info(f"Загружаем страницу: {url}")
            response = await page.goto(url, wait_until=self.config.wait_for_load_state)
            
            # Ждем дополнительный селектор если указан
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=10000)
                except Exception as e:
                    logger.warning(f"Селектор {wait_for_selector} не найден: {e}")
            
            # Небольшая дополнительная пауза для загрузки динамического контента
            await page.wait_for_timeout(2000)
            
            # Получаем данные страницы
            title = await page.title()
            content = await page.content()
            url_final = page.url
            
            # Извлекаем метаданные с безопасной обработкой
            try:
                meta_description = await page.get_attribute('meta[name="description"]', 'content', timeout=5000) or ""
            except:
                meta_description = ""
                
            try:
                meta_keywords = await page.get_attribute('meta[name="keywords"]', 'content', timeout=5000) or ""
            except:
                meta_keywords = ""
            
            # Получаем все ссылки
            links = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links.map(link => ({
                        href: link.href,
                        text: link.textContent.trim(),
                        title: link.title || ''
                    })).filter(link => link.href && link.text);
                }
            """)
            
            # Получаем изображения
            images = await page.evaluate("""
                () => {
                    const images = Array.from(document.querySelectorAll('img[src]'));
                    return images.map(img => ({
                        src: img.src,
                        alt: img.alt || '',
                        title: img.title || ''
                    })).filter(img => img.src);
                }
            """)
            
            # Статус ответа
            status_code = response.status if response else 200
            
            return {
                'url': url_final,
                'title': title,
                'content': content,
                'meta_description': meta_description,
                'meta_keywords': meta_keywords,
                'links': links[:50],  # Ограничиваем количество ссылок
                'images': images[:20],  # Ограничиваем количество изображений
                'status_code': status_code,
                'success': True,
                'method': 'playwright'
            }
            
        except Exception as e:
            logger.error(f"Ошибка загрузки страницы {url}: {e}")
            return {
                'url': url,
                'error': str(e),
                'success': False,
                'method': 'playwright'
            }
        finally:
            if page:
                await page.close()
                
    async def get_page_screenshot(self, url: str, path: str = None) -> Optional[bytes]:
        """Получение скриншота страницы"""
        if not self.context:
            raise RuntimeError("Playwright не инициализирован")
            
        page = None
        try:
            page = await self.context.new_page()
            await page.goto(url, wait_until=self.config.wait_for_load_state)
            await page.wait_for_timeout(2000)
            
            screenshot = await page.screenshot(
                path=path,
                full_page=True,
                type='png'
            )
            
            return screenshot
            
        except Exception as e:
            logger.error(f"Ошибка создания скриншота {url}: {e}")
            return None
        finally:
            if page:
                await page.close()
                
    async def check_page_performance(self, url: str) -> Dict[str, Any]:
        """Анализ производительности страницы"""
        if not self.context:
            raise RuntimeError("Playwright не инициализирован")
            
        page = None
        try:
            page = await self.context.new_page()
            
            # Засекаем время загрузки
            start_time = asyncio.get_event_loop().time()
            await page.goto(url, wait_until="networkidle")
            load_time = asyncio.get_event_loop().time() - start_time
            
            # Получаем метрики производительности
            performance = await page.evaluate("""
                () => {
                    const navigation = performance.getEntriesByType('navigation')[0];
                    return {
                        loadEventEnd: navigation.loadEventEnd,
                        domContentLoadedEventEnd: navigation.domContentLoadedEventEnd,
                        responseEnd: navigation.responseEnd,
                        transferSize: navigation.transferSize,
                        encodedBodySize: navigation.encodedBodySize
                    };
                }
            """)
            
            return {
                'url': url,
                'load_time': round(load_time, 2),
                'performance_metrics': performance,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Ошибка анализа производительности {url}: {e}")
            return {
                'url': url,
                'error': str(e),
                'success': False
            }
        finally:
            if page:
                await page.close()


async def fetch_with_playwright(
    url: str, 
    config: Optional[PlaywrightConfig] = None,
    wait_for_selector: Optional[str] = None
) -> Dict[str, Any]:
    """
    Удобная функция для получения контента страницы через Playwright
    
    Args:
        url: URL страницы
        config: Конфигурация Playwright
        wait_for_selector: CSS селектор для ожидания
        
    Returns:
        Словарь с данными страницы
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("Playwright не доступен")
        
    async with PlaywrightFetcher(config) as fetcher:
        return await fetcher.fetch_page_content(url, wait_for_selector)


# Конфигурация по умолчанию из настроек
def get_default_playwright_config() -> PlaywrightConfig:
    """Получение конфигурации Playwright из настроек приложения"""
    return PlaywrightConfig(
        headless=getattr(settings, 'PLAYWRIGHT_HEADLESS', True),
        timeout=getattr(settings, 'PLAYWRIGHT_TIMEOUT', 30000),
        wait_for_load_state=getattr(settings, 'PLAYWRIGHT_WAIT_FOR_LOAD_STATE', 'networkidle')
    )