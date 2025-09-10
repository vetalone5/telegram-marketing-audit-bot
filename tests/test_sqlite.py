import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from app.storage.sqlite import (
    Database, get_user_sheet_id, set_user_sheet_id,
    ensure_user_limit, can_run, increment_counter, set_limit,
    save_pending_result, fetch_unwritten_results, mark_written
)


class TestSQLiteDatabase:
    """Тесты для SQLite базы данных"""
    
    @pytest.fixture
    def temp_db(self):
        """Временная база данных для тестов"""
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        
        # Подменяем глобальный путь к БД
        from app.storage.sqlite import db
        original_path = db.db_path
        db.db_path = Path(temp_path)
        
        # Пересоздаем БД с новым путем
        db._init_db()
        
        yield db
        
        # Восстанавливаем оригинальный путь
        db.db_path = original_path
        try:
            os.unlink(temp_path)
        except:
            pass
    
    @pytest.mark.asyncio
    async def test_user_sheet_operations(self, temp_db):
        """Тестирование операций с настройками пользователей"""
        user_id = "test_user_123"
        sheet_id = "test_sheet_456"
        
        # Изначально пользователя нет
        result = await get_user_sheet_id(user_id)
        assert result is None
        
        # Устанавливаем sheet_id
        await set_user_sheet_id(user_id, sheet_id)
        
        # Проверяем что сохранилось
        result = await get_user_sheet_id(user_id)
        assert result == sheet_id
        
        # Обновляем sheet_id
        new_sheet_id = "new_sheet_789"
        await set_user_sheet_id(user_id, new_sheet_id)
        
        result = await get_user_sheet_id(user_id)
        assert result == new_sheet_id
    
    @pytest.mark.asyncio
    async def test_user_limits_operations(self, temp_db):
        """Тестирование лимитов пользователей"""
        user_id = "test_user_limits"
        default_limit = 10
        
        # Убеждаемся что лимит создается
        await ensure_user_limit(user_id, default_limit)
        
        # Пользователь может выполнять запросы
        can_execute = await can_run(user_id, default_limit)
        assert can_execute is True
        
        # Увеличиваем счетчик несколько раз
        for i in range(5):
            await increment_counter(user_id)
            can_execute = await can_run(user_id, default_limit)
            assert can_execute is True  # Еще в лимите
        
        # Увеличиваем до лимита
        for i in range(5):
            await increment_counter(user_id)
        
        # Теперь лимит исчерпан
        can_execute = await can_run(user_id, default_limit)
        assert can_execute is False
        
        # Устанавливаем новый лимит
        await set_limit(user_id, 20)
        can_execute = await can_run(user_id, default_limit)
        assert can_execute is True  # Снова можем выполнять
    
    @pytest.mark.asyncio
    async def test_pending_results_operations(self, temp_db):
        """Тестирование отложенных результатов"""
        user_id = "test_pending_user"
        url = "https://example.com"
        result_json = '{"test": "data", "analysis": "complete"}'
        
        # Сохраняем результат
        result_id = await save_pending_result(user_id, url, result_json)
        assert result_id is not None
        assert result_id > 0
        
        # Получаем неперенесенные результаты
        results = await fetch_unwritten_results(user_id)
        assert len(results) == 1
        assert results[0]['user_id'] == user_id
        assert results[0]['url'] == url
        assert results[0]['result_json'] == result_json
        assert results[0]['written'] == 0
        
        # Отмечаем как перенесенный
        await mark_written(result_id)
        
        # Теперь неперенесенных результатов нет
        results = await fetch_unwritten_results(user_id)
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_multiple_pending_results(self, temp_db):
        """Тестирование нескольких отложенных результатов"""
        user_id = "test_multiple_user"
        
        # Сохраняем несколько результатов
        urls = ["https://site1.com", "https://site2.com", "https://site3.com"]
        result_ids = []
        
        for i, url in enumerate(urls):
            result_json = f'{{"test": "data{i}", "url": "{url}"}}'
            result_id = await save_pending_result(user_id, url, result_json)
            result_ids.append(result_id)
        
        # Проверяем что все сохранились
        results = await fetch_unwritten_results(user_id)
        assert len(results) == 3
        
        # Отмечаем первый как перенесенный
        await mark_written(result_ids[0])
        
        # Остается 2 неперенесенных
        results = await fetch_unwritten_results(user_id)
        assert len(results) == 2
        
        # Проверяем что остались правильные
        remaining_urls = [r['url'] for r in results]
        assert urls[1] in remaining_urls
        assert urls[2] in remaining_urls
        assert urls[0] not in remaining_urls
    
    @pytest.mark.asyncio
    async def test_different_users_isolation(self, temp_db):
        """Тестирование изоляции данных разных пользователей"""
        user1 = "user_1"
        user2 = "user_2"
        
        # Устанавливаем разные sheet_id
        await set_user_sheet_id(user1, "sheet_1")
        await set_user_sheet_id(user2, "sheet_2")
        
        # Проверяем изоляцию
        assert await get_user_sheet_id(user1) == "sheet_1"
        assert await get_user_sheet_id(user2) == "sheet_2"
        
        # Сохраняем результаты для разных пользователей
        await save_pending_result(user1, "https://site1.com", '{"user": 1}')
        await save_pending_result(user2, "https://site2.com", '{"user": 2}')
        
        # Проверяем изоляцию результатов
        results1 = await fetch_unwritten_results(user1)
        results2 = await fetch_unwritten_results(user2)
        
        assert len(results1) == 1
        assert len(results2) == 1
        assert results1[0]['user_id'] == user1
        assert results2[0]['user_id'] == user2