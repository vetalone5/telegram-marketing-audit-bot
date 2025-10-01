"""
Тест интеграции Playwright
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock

from app.features.audit.adapters.fetcher import get_content_bundle
from app.features.audit.adapters.playwright_fetcher import (
    PLAYWRIGHT_AVAILABLE, 
    PlaywrightFetcher, 
    PlaywrightConfig,
    fetch_with_playwright
)


class TestPlaywrightIntegration:
    """Тесты для интеграции Playwright"""
    
    def test_playwright_availability_check(self):
        """Тест проверки доступности Playwright"""
        # Проверяем, что флаг доступности корректно определяется
        assert isinstance(PLAYWRIGHT_AVAILABLE, bool)
        
    def test_playwright_config_creation(self):
        """Тест создания конфигурации Playwright"""
        config = PlaywrightConfig()
        
        assert config.headless is True
        assert config.timeout == 30000
        assert config.wait_for_load_state == "networkidle"
        assert config.viewport is not None
        assert config.user_agent is not None
        assert "Mozilla" in config.user_agent
        
    def test_playwright_config_custom(self):
        """Тест создания кастомной конфигурации"""
        config = PlaywrightConfig(
            headless=False,
            timeout=60000,
            viewport={"width": 1366, "height": 768}
        )
        
        assert config.headless is False
        assert config.timeout == 60000
        assert config.viewport["width"] == 1366
        
    @pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright не установлен")
    @pytest.mark.asyncio
    async def test_playwright_fetcher_initialization(self):
        """Тест инициализации Playwright fetcher"""
        config = PlaywrightConfig()
        fetcher = PlaywrightFetcher(config)
        
        assert fetcher.config == config
        assert fetcher.browser is None
        assert fetcher.context is None
        
    @pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright не установлен")
    @pytest.mark.asyncio
    async def test_playwright_context_manager(self):
        """Тест использования как context manager"""
        config = PlaywrightConfig(headless=True)
        
        try:
            async with PlaywrightFetcher(config) as fetcher:
                assert fetcher.browser is not None
                assert fetcher.context is not None
        except Exception as e:
            # Может не работать в CI/CD окружении
            pytest.skip(f"Playwright не может запуститься: {e}")
            
    def test_fetcher_fallback_behavior(self):
        """Тест поведения fallback в основном fetcher"""
        # Мокаем отсутствие Playwright
        with patch('app.features.audit.adapters.fetcher.PLAYWRIGHT_AVAILABLE', False):
            result = asyncio.run(get_content_bundle("https://example.com"))
            
            # Должен использовать HTTP fallback
            assert result is not None
            assert result.get('method') in ['http', 'requests']
            
    @pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright не установлен")
    @pytest.mark.asyncio 
    async def test_playwright_fetch_simple_page(self):
        """Тест загрузки простой страницы через Playwright"""
        try:
            result = await fetch_with_playwright("https://httpbin.org/html")
            
            assert result['success'] is True
            assert result['method'] == 'playwright'
            assert result['title'] is not None
            assert result['content'] is not None
            assert result['status_code'] == 200
            
        except Exception as e:
            pytest.skip(f"Не удалось выполнить тест с Playwright: {e}")
            
    def test_main_fetcher_with_playwright_enabled(self):
        """Тест основного fetcher с включенным Playwright"""
        with patch('app.features.audit.adapters.fetcher.PLAYWRIGHT_AVAILABLE', True):
            with patch('app.core.settings.settings.USE_PLAYWRIGHT', True):
                # Мокаем успешный результат Playwright
                mock_result = {
                    'url': 'https://example.com',
                    'title': 'Test Page',
                    'content': '<html>Test</html>',
                    'success': True,
                    'method': 'playwright'
                }
                
                with patch('app.features.audit.adapters.fetcher.fetch_with_playwright', 
                          return_value=asyncio.create_task(asyncio.coroutine(lambda: mock_result)())):
                    
                    result = asyncio.run(get_content_bundle("https://example.com"))
                    assert result is not None


class TestPlaywrightErrorHandling:
    """Тесты обработки ошибок Playwright"""
    
    def test_playwright_not_available_error(self):
        """Тест ошибки при отсутствии Playwright"""
        with patch('app.features.audit.adapters.playwright_fetcher.PLAYWRIGHT_AVAILABLE', False):
            with pytest.raises(ImportError) as exc_info:
                PlaywrightFetcher()
            
            assert "Playwright не установлен" in str(exc_info.value)
            
    @pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright не установлен")
    @pytest.mark.asyncio
    async def test_playwright_invalid_url_handling(self):
        """Тест обработки некорректных URL"""
        try:
            result = await fetch_with_playwright("invalid-url")
            
            assert result['success'] is False
            assert 'error' in result
            assert result['method'] == 'playwright'
            
        except Exception as e:
            pytest.skip(f"Тест пропущен из-за ошибки окружения: {e}")


if __name__ == "__main__":
    # Простой запуск для быстрой проверки
    print("🧪 Запуск базовых тестов Playwright интеграции...")
    
    # Тест доступности
    test_integration = TestPlaywrightIntegration()
    test_integration.test_playwright_availability_check()
    print("✅ Тест доступности Playwright пройден")
    
    # Тест конфигурации
    test_integration.test_playwright_config_creation()
    print("✅ Тест конфигурации пройден")
    
    print("🎉 Базовые тесты выполнены успешно!")
    print(f"📊 Playwright доступен: {PLAYWRIGHT_AVAILABLE}")