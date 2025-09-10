import sys
from pathlib import Path
from loguru import logger


def setup_logging():
    """Настройка логирования для приложения"""
    
    # Удаляем стандартный обработчик loguru
    logger.remove()
    
    # Поток в консоль с цветами
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        level="INFO",
        colorize=True
    )
    
    # Создаем папку для логов если не существует
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Поток в файл с ротацией
    logger.add(
        "logs/bot.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",  # Ротация по размеру
        retention="7 days",  # Хранение 7 дней
        compression="zip",  # Сжатие старых логов
        encoding="utf-8"
    )
    
    # Отдельный файл для ошибок
    logger.add(
        "logs/errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="5 MB",
        retention="14 days",  # Ошибки храним дольше
        compression="zip",
        encoding="utf-8"
    )
    
    logger.info("Логирование настроено успешно")


# Настраиваем логирование при импорте модуля
setup_logging()