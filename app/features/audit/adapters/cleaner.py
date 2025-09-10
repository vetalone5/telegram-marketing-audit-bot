import re
from bs4 import BeautifulSoup
from bs4 import Comment
from loguru import logger


def clean_html(html: str) -> str:
    """
    Очистка HTML и преобразование в нормализованный текст
    
    Args:
        html: HTML содержимое для очистки
        
    Returns:
        Очищенный текст без лишних пробелов и служебных элементов
    """
    try:
        if not html or not html.strip():
            return ""
        
        # Создаем BeautifulSoup объект
        soup = BeautifulSoup(html, 'html.parser')
        
        # Удаляем ненужные теги
        for tag in soup(["script", "style", "noscript", "meta", "link", "head"]):
            tag.decompose()
        
        # Удаляем комментарии (исправленная версия)
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        # Извлекаем текст
        text = soup.get_text()
        
        # Нормализуем пробелы и переносы строк
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        
        # Убираем лишние пробелы в начале и конце строк
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)
        
        # Общая очистка
        text = text.strip()
        
        logger.debug(f"HTML очищен: {len(html)} символов -> {len(text)} символов")
        return text
        
    except Exception as e:
        logger.error(f"Ошибка очистки HTML: {e}")
        # Возвращаем исходный текст в случае ошибки, но без тегов
        try:
            # Простая очистка без BeautifulSoup
            text = re.sub(r'<[^>]+>', '', html)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
        except:
            return html[:1000]  # В крайнем случае возвращаем первые 1000 символов


def extract_visible_text(html: str) -> str:
    """
    Извлечение только видимого текста из HTML
    
    Args:
        html: HTML содержимое
        
    Returns:
        Видимый текст без скрытых элементов
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Удаляем скрытые элементы
        for tag in soup.find_all(attrs={"style": re.compile(r"display\s*:\s*none", re.I)}):
            tag.decompose()
        
        for tag in soup.find_all(attrs={"class": re.compile(r"hidden", re.I)}):
            tag.decompose()
            
        # Удаляем служебные теги
        for tag in soup(["script", "style", "noscript", "meta", "link", "head", "nav", "footer"]):
            tag.decompose()
        
        # Извлекаем весь видимый текст (убрано приоритизирование main)
        text = soup.get_text()
        
        # Очистка
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
        
    except Exception as e:
        logger.error(f"Ошибка извлечения видимого текста: {e}")
        return clean_html(html)


def remove_navigation_noise(text: str) -> str:
    """
    Удаление навигационного шума из текста
    
    Args:
        text: Текст для очистки
        
    Returns:
        Текст без навигационных элементов
    """
    try:
        # Паттерны для удаления навигационных элементов
        noise_patterns = [
            r'главная\s+о\s+нас\s+услуги\s+контакты',
            r'home\s+about\s+services\s+contact',
            r'меню\s+\|',
            r'©\s*\d{4}.*?права защищены',
            r'cookie.*?согласие',
            r'политика конфиденциальности',
            r'пользовательское соглашение',
        ]
        
        for pattern in noise_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Удаляем повторяющиеся фразы (больше 3 раз)
        words = text.split()
        if len(words) > 10:
            word_counts = {}
            for word in words:
                if len(word) > 3:  # Только длинные слова
                    word_counts[word.lower()] = word_counts.get(word.lower(), 0) + 1
            
            # Удаляем слова которые повторяются слишком часто
            filtered_words = []
            for word in words:
                if word_counts.get(word.lower(), 0) <= 3:
                    filtered_words.append(word)
            
            text = ' '.join(filtered_words)
        
        return text.strip()
        
    except Exception as e:
        logger.error(f"Ошибка удаления навигационного шума: {e}")
        return text