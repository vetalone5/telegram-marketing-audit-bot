# Механизмы повторных попыток

from functools import wraps
from typing import Any, Callable, TypeVar
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
from loguru import logger
import httpx

F = TypeVar('F', bound=Callable[..., Any])


def retry_on_network_error(func: F) -> F:
    """
    Декоратор для повторных попыток при сетевых ошибках
    Максимум 2 попытки с задержкой 1с, затем 3с
    """
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1) + wait_fixed(2),  # 1с + 2с = 3с на вторую попытку
        retry=retry_if_exception_type((
            httpx.RequestError,
            httpx.TimeoutException,
            ConnectionError,
            TimeoutError
        )),
        before_sleep=before_sleep_log(logger, "WARNING"),
        after=after_log(logger, "INFO")
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    
    return wrapper


def retry_on_llm_error(func: F) -> F:
    """
    Декоратор для повторных попыток при ошибках LLM
    Максимум 2 попытки с задержкой 1с, затем 3с
    """
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1) + wait_fixed(2),  # 1с + 2с = 3с на вторую попытку
        retry=retry_if_exception_type((
            Exception,  # Ловим общие ошибки API
        )),
        before_sleep=before_sleep_log(logger, "WARNING"),
        after=after_log(logger, "INFO")
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    
    return wrapper


def retry_on_api_error(func: F) -> F:
    """
    Универсальный декоратор для API вызовов
    Максимум 2 попытки с задержкой 1с, затем 3с
    """
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1) + wait_fixed(2),  # 1с + 2с = 3с на вторую попытку
        retry=retry_if_exception_type((
            httpx.RequestError,
            httpx.TimeoutException,
            ConnectionError,
            TimeoutError,
            Exception
        )),
        before_sleep=before_sleep_log(logger, "WARNING", exc_info=True),
        after=after_log(logger, "INFO")
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Успешный вызов {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"Ошибка в {func.__name__}: {e}")
            raise
    
    return wrapper