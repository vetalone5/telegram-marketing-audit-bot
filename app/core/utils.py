# Вспомогательные утилиты
import re
from urllib.parse import urlparse, urlunparse
from loguru import logger


def normalize_url(s: str) -> str:
    """
    Нормализация URL с поддержкой различных форматов
    
    Args:
        s: URL строка для нормализации
        
    Returns:
        Нормализованный URL с https схемой
        
    Examples:
        normalize_url("google.com") -> "https://google.com"
        normalize_url("www.google.com") -> "https://google.com"
        normalize_url("http://google.com") -> "https://google.com"
        normalize_url("  https://www.google.com/  ") -> "https://google.com"
    """
    if not s or not isinstance(s, str):
        return ""
    
    # Убираем пробелы
    url = s.strip()
    
    if not url:
        return ""
    
    # Если нет схемы, добавляем https://
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        # Парсим URL
        parsed = urlparse(url)
        
        # Принудительно используем https
        scheme = 'https'
        
        # Убираем www. из начала домена
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        
        # Убираем trailing slash если нет пути
        path = parsed.path
        if path == '/':
            path = ''
        
        # Собираем нормализованный URL
        normalized = urlunparse((
            scheme,
            netloc,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        logger.debug(f"URL нормализован: {s} -> {normalized}")
        return normalized
        
    except Exception as e:
        logger.warning(f"Ошибка нормализации URL '{s}': {e}")
        return ""


def is_valid_url(url: str) -> bool:
    """
    Проверка валидности URL
    
    Args:
        url: URL для проверки
        
    Returns:
        True если URL валидный
    """
    if not url:
        return False
        
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def extract_domain(url: str) -> str:
    """
    Извлечение домена из URL
    
    Args:
        url: URL для извлечения домена
        
    Returns:
        Доменное имя или пустая строка
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Убираем www. если есть
        if domain.startswith('www.'):
            domain = domain[4:]
            
        return domain
    except Exception as e:
        logger.warning(f"Ошибка извлечения домена из '{url}': {e}")
        return ""


def clean_text(text: str) -> str:
    """
    Очистка текста от лишних символов и пробелов
    
    Args:
        text: Текст для очистки
        
    Returns:
        Очищенный текст
    """
    if not text:
        return ""
    
    # Убираем лишние пробелы и переносы строк
    cleaned = re.sub(r'\s+', ' ', text.strip())
    
    # Убираем специальные символы которые могут мешать
    cleaned = re.sub(r'[^\w\s\-.,!?@#$%&*()+=<>:;/\\|{}[\]~`]', '', cleaned)
    
    return cleaned