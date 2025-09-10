import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from app.features.audit.services.run_audit import run_audit
from app.features.audit.services.persist import write_or_defer, flush_pending_to_user_sheet


class TestE2EWorkflow:
    """E2E тесты для полного цикла анализа"""
    
    @pytest.mark.asyncio
    async def test_full_audit_cycle_without_sheet(self):
        """Полный цикл анализа без подключенной таблицы"""
        user_id = "test_e2e_user"
        url = "https://example.com"
        
        # Mock для get_content_bundle
        mock_bundle = {
            "home_text": "Главная страница с оффером и CTA. Цены от 1000 руб.",
            "pricing_text": "Детальные цены: Базовый 1000, Премиум 2000",
            "pricing_url": "https://example.com/pricing"
        }
        
        # Mock для analyze_content
        mock_full_result = Mock()
        mock_full_result.model_dump.return_value = {
            "offer_first_screen": "Увеличим продажи в 2 раза",
            "cta_first_screen": "Получить консультацию",
            "prices_tariffs": "Базовый 1000, Премиум 2000 (цены: https://example.com/pricing)"
        }
        mock_short_summary = ["Хороший оффер", "Понятные цены", "Нужно добавить гарантии"]
        
        # Исправляем пути для моков - указываем где функции импортируются, а не где определены
        with patch('app.features.audit.services.run_audit.get_content_bundle', new_callable=AsyncMock) as mock_get_content, \
             patch('app.features.audit.services.run_audit.analyze_content', new_callable=AsyncMock) as mock_analyze, \
             patch('app.features.audit.services.run_audit.get_user_sheet_id', new_callable=AsyncMock) as mock_get_sheet, \
             patch('app.features.audit.services.run_audit.ensure_user_limit', new_callable=AsyncMock), \
             patch('app.features.audit.services.run_audit.can_run', new_callable=AsyncMock) as mock_can_run, \
             patch('app.features.audit.services.run_audit.increment_counter', new_callable=AsyncMock), \
             patch('app.features.audit.services.run_audit.write_or_defer', new_callable=AsyncMock) as mock_write:
            
            # Настройка моков
            mock_get_content.return_value = mock_bundle
            mock_analyze.return_value = (mock_full_result, mock_short_summary)
            mock_get_sheet.return_value = None  # Таблица не подключена
            mock_can_run.return_value = True
            
            # Выполняем анализ
            result = await run_audit(user_id, url)
            
            # Проверки
            assert result["ok"] is True
            assert result["written_now"] is False  # Таблица не подключена
            assert result["short_summary"] == mock_short_summary
            
            # Проверяем вызовы
            mock_get_content.assert_called_once()
            mock_analyze.assert_called_once()
            mock_write.assert_called_once()  # write_or_defer всегда вызывается
    
    @pytest.mark.asyncio
    async def test_full_audit_cycle_with_sheet(self):
        """Полный цикл анализа с подключенной таблицей"""
        user_id = "test_e2e_user_with_sheet"
        url = "https://example.com"
        
        with patch('app.features.audit.services.run_audit.get_content_bundle', new_callable=AsyncMock) as mock_get_content, \
             patch('app.features.audit.services.run_audit.analyze_content', new_callable=AsyncMock) as mock_analyze, \
             patch('app.features.audit.services.run_audit.get_user_sheet_id', new_callable=AsyncMock) as mock_get_sheet, \
             patch('app.features.audit.services.run_audit.ensure_user_limit', new_callable=AsyncMock), \
             patch('app.features.audit.services.run_audit.can_run', new_callable=AsyncMock) as mock_can_run, \
             patch('app.features.audit.services.run_audit.increment_counter', new_callable=AsyncMock), \
             patch('app.features.audit.services.run_audit.write_or_defer', new_callable=AsyncMock) as mock_write:
            
            # Настройка моков
            mock_bundle = {
                "home_text": "Контент главной страницы",
                "pricing_text": None,
                "pricing_url": None
            }
            mock_full_result = Mock()
            mock_full_result.model_dump.return_value = {"offer_first_screen": "Тестовый оффер"}
            mock_short_summary = ["Результат 1", "Результат 2"]
            
            mock_get_content.return_value = mock_bundle
            mock_analyze.return_value = (mock_full_result, mock_short_summary)
            mock_get_sheet.return_value = "test_sheet_123"  # Таблица подключена
            mock_can_run.return_value = True
            
            # Выполняем анализ
            result = await run_audit(user_id, url)
            
            # Проверки
            assert result["ok"] is True
            assert result["written_now"] is True  # Таблица подключена
            assert result["short_summary"] == mock_short_summary
            
            # Проверяем что write_or_defer вызван
            mock_write.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_audit_limit_exceeded(self):
        """Тест превышения лимита анализов"""
        user_id = "test_limited_user"
        url = "https://example.com"
        
        with patch('app.features.audit.services.run_audit.ensure_user_limit', new_callable=AsyncMock), \
             patch('app.features.audit.services.run_audit.can_run', new_callable=AsyncMock) as mock_can_run:
            
            # Лимит превышен
            mock_can_run.return_value = False
            
            # Выполняем анализ
            result = await run_audit(user_id, url)
            
            # Проверки
            assert result["ok"] is False
            assert result["reason"] == "limit"
    
    @pytest.mark.asyncio
    async def test_content_fetching_failure(self):
        """Тест ошибки при загрузке контента"""
        user_id = "test_fetch_error_user"
        url = "https://invalid-url.com"
        
        with patch('app.features.audit.services.run_audit.get_content_bundle', new_callable=AsyncMock) as mock_get_content, \
             patch('app.features.audit.services.run_audit.ensure_user_limit', new_callable=AsyncMock), \
             patch('app.features.audit.services.run_audit.can_run', new_callable=AsyncMock) as mock_can_run:
            
            # Настройка моков
            mock_can_run.return_value = True
            mock_get_content.return_value = {"home_text": ""}  # Пустой контент
            
            # Выполняем анализ
            result = await run_audit(user_id, url)
            
            # Проверки
            assert result["ok"] is False
            assert result["reason"] == "fetch_failed"
    
    @pytest.mark.asyncio
    async def test_pending_results_flush(self):
        """Тест переноса отложенных результатов"""
        user_id = "test_flush_user"
        
        # Mock данные отложенных результатов
        mock_pending_results = [
            {
                "id": 1,
                "user_id": user_id,
                "url": "https://site1.com",
                "result_json": '{"full_result": {"offer_first_screen": "Test"}}',
                "created_at": "2025-01-01 12:00:00",
                "written": 0
            },
            {
                "id": 2,
                "user_id": user_id,
                "url": "https://site2.com", 
                "result_json": '{"full_result": {"offer_first_screen": "Test2"}}',
                "created_at": "2025-01-01 13:00:00",
                "written": 0
            }
        ]
        
        with patch('app.features.audit.services.persist.get_user_sheet_id', new_callable=AsyncMock) as mock_get_sheet, \
             patch('app.features.audit.services.persist.fetch_unwritten_results', new_callable=AsyncMock) as mock_fetch, \
             patch('app.features.audit.services.persist.ensure_headers', new_callable=AsyncMock), \
             patch('app.features.audit.services.persist.write_row', new_callable=AsyncMock) as mock_write_row, \
             patch('app.features.audit.services.persist.mark_written', new_callable=AsyncMock) as mock_mark:
            
            # Настройка моков
            mock_get_sheet.return_value = "test_sheet_123"
            mock_fetch.return_value = mock_pending_results
            
            # Выполняем перенос
            count = await flush_pending_to_user_sheet(user_id)
            
            # Проверки
            assert count == 2
            assert mock_write_row.call_count == 2
            assert mock_mark.call_count == 2
    
    @pytest.mark.asyncio
    async def test_write_or_defer_with_sheet(self):
        """Тест записи результата в подключенную таблицу"""
        user_id = "test_write_user"
        url = "https://example.com"
        result_json = '{"full_result": {"offer_first_screen": "Тестовый оффер"}}'
        
        with patch('app.features.audit.services.persist.get_user_sheet_id', new_callable=AsyncMock) as mock_get_sheet, \
             patch('app.features.audit.services.persist.ensure_headers', new_callable=AsyncMock), \
             patch('app.features.audit.services.persist.write_row', new_callable=AsyncMock) as mock_write_row:
            
            # Настройка моков
            mock_get_sheet.return_value = "test_sheet_123"
            
            # Выполняем запись
            await write_or_defer(user_id, url, result_json)
            
            # Проверки
            mock_write_row.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_write_or_defer_without_sheet(self):
        """Тест отложенного сохранения без подключенной таблицы"""
        user_id = "test_defer_user"
        url = "https://example.com"
        result_json = '{"full_result": {"offer_first_screen": "Тестовый оффер"}}'
        
        with patch('app.features.audit.services.persist.get_user_sheet_id', new_callable=AsyncMock) as mock_get_sheet, \
             patch('app.features.audit.services.persist.save_pending_result', new_callable=AsyncMock) as mock_save:
            
            # Настройка моков
            mock_get_sheet.return_value = None  # Таблица не подключена
            mock_save.return_value = 123  # ID сохраненного результата
            
            # Выполняем отложенное сохранение
            await write_or_defer(user_id, url, result_json)
            
            # Проверки
            mock_save.assert_called_once_with(user_id, url, result_json)