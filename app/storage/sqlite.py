import sqlite3
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

# Путь к базе данных
DB_PATH = Path("app") / "storage" / "bot.db"


class Database:
    """Класс для работы с SQLite базой данных"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()
    
    def _init_db(self):
        """Инициализация базы данных и создание таблиц"""
        # Создаем папку если не существует
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблица настроек пользователей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users_settings (
                    user_id TEXT PRIMARY KEY,
                    sheet_id TEXT
                )
            """)
            
            # Таблица лимитов пользователей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users_limits (
                    user_id TEXT PRIMARY KEY,
                    current INTEGER DEFAULT 0,
                    max_limit INTEGER
                )
            """)
            
            # Таблица отложенных результатов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    written INTEGER DEFAULT 0
                )
            """)
            
            conn.commit()
            logger.info("База данных инициализирована")
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Выполнение SELECT запроса"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Выполнение INSERT/UPDATE/DELETE запроса"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid or cursor.rowcount


# Глобальный экземпляр базы данных
db = Database()


# Функции для работы с настройками пользователей
async def get_user_sheet_id(user_id: str) -> Optional[str]:
    """Получить sheet_id пользователя"""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            db.execute_query,
            "SELECT sheet_id FROM users_settings WHERE user_id = ?",
            (user_id,)
        )
        
        if result:
            sheet_id = result[0]['sheet_id']
            logger.debug(f"Получен sheet_id для {user_id}: {sheet_id}")
            return sheet_id
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка получения sheet_id для {user_id}: {e}")
        return None


async def set_user_sheet_id(user_id: str, sheet_id: str) -> None:
    """Установить sheet_id пользователя"""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            db.execute_update,
            "INSERT OR REPLACE INTO users_settings (user_id, sheet_id) VALUES (?, ?)",
            (user_id, sheet_id)
        )
        
        logger.info(f"Установлен sheet_id для {user_id}: {sheet_id}")
        
    except Exception as e:
        logger.error(f"Ошибка установки sheet_id для {user_id}: {e}")
        raise


# Функции для работы с лимитами пользователей
async def ensure_user_limit(user_id: str, default_limit: int) -> None:
    """Создать запись лимита если её нет"""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            db.execute_update,
            "INSERT OR IGNORE INTO users_limits (user_id, current, max_limit) VALUES (?, 0, ?)",
            (user_id, default_limit)
        )
        
        logger.debug(f"Лимит пользователя {user_id} проверен/создан")
        
    except Exception as e:
        logger.error(f"Ошибка создания лимита для {user_id}: {e}")
        raise


async def can_run(user_id: str, default_limit: int) -> bool:
    """Проверить может ли пользователь запустить анализ"""
    try:
        # Убедимся что запись лимита существует
        await ensure_user_limit(user_id, default_limit)
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            db.execute_query,
            "SELECT current, max_limit FROM users_limits WHERE user_id = ?",
            (user_id,)
        )
        
        if result:
            current = result[0]['current']
            max_limit = result[0]['max_limit']
            can_execute = current < max_limit
            
            logger.debug(f"Лимит {user_id}: {current}/{max_limit}, можно выполнить: {can_execute}")
            return can_execute
        
        return False
        
    except Exception as e:
        logger.error(f"Ошибка проверки лимита для {user_id}: {e}")
        return False


async def increment_counter(user_id: str) -> None:
    """Увеличить счетчик использования"""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            db.execute_update,
            "UPDATE users_limits SET current = current + 1 WHERE user_id = ?",
            (user_id,)
        )
        
        logger.debug(f"Счетчик для {user_id} увеличен")
        
    except Exception as e:
        logger.error(f"Ошибка увеличения счетчика для {user_id}: {e}")
        raise


async def set_limit(user_id: str, n: int) -> None:
    """Установить лимит пользователя"""
    try:
        loop = asyncio.get_event_loop()
        # Сначала убеждаемся что запись существует
        await ensure_user_limit(user_id, n)
        
        # Просто обновляем max_limit, сохраняя current
        await loop.run_in_executor(
            None,
            db.execute_update,
            "UPDATE users_limits SET max_limit = ? WHERE user_id = ?",
            (n, user_id)
        )
        
        logger.info(f"Лимит для {user_id} установлен: {n}")
        
    except Exception as e:
        logger.error(f"Ошибка установки лимита для {user_id}: {e}")
        raise


# Функции для работы с отложенными результатами
async def save_pending_result(user_id: str, url: str, result_json: str) -> int:
    """Сохранить отложенный результат"""
    try:
        created_at = datetime.now().isoformat()
        loop = asyncio.get_event_loop()
        result_id = await loop.run_in_executor(
            None,
            db.execute_update,
            "INSERT INTO pending_results (user_id, url, result_json, created_at) VALUES (?, ?, ?, ?)",
            (user_id, url, result_json, created_at)
        )
        
        logger.info(f"Сохранен отложенный результат {result_id} для {user_id}")
        return result_id
        
    except Exception as e:
        logger.error(f"Ошибка сохранения отложенного результата для {user_id}: {e}")
        raise


async def fetch_unwritten_results(user_id: str) -> List[Dict[str, Any]]:
    """Получить неперенесенные результаты пользователя"""
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            db.execute_query,
            "SELECT * FROM pending_results WHERE user_id = ? AND written = 0 ORDER BY created_at",
            (user_id,)
        )
        
        logger.debug(f"Найдено {len(results)} неперенесенных результатов для {user_id}")
        return results
        
    except Exception as e:
        logger.error(f"Ошибка получения отложенных результатов для {user_id}: {e}")
        return []


async def mark_written(result_id: int) -> None:
    """Отметить результат как перенесенный"""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            db.execute_update,
            "UPDATE pending_results SET written = 1 WHERE id = ?",
            (result_id,)
        )
        
        logger.debug(f"Результат {result_id} отмечен как перенесенный")
        
    except Exception as e:
        logger.error(f"Ошибка отметки результата {result_id}: {e}")
        raise