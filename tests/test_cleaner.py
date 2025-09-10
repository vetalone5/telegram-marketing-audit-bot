import pytest
from app.features.audit.adapters.cleaner import clean_html, extract_visible_text, remove_navigation_noise


class TestHtmlCleaner:
    """Тесты для модуля очистки HTML"""
    
    def test_clean_html_basic(self):
        """Базовая очистка HTML"""
        html = """
        <html>
            <head><title>Test</title></head>
            <body>
                <script>console.log('test');</script>
                <style>.test { color: red; }</style>
                <h1>Заголовок</h1>
                <p>Параграф текста</p>
            </body>
        </html>
        """
        result = clean_html(html)
        assert "Заголовок" in result
        assert "Параграф текста" in result
        assert "console.log" not in result
        assert "color: red" not in result
    
    def test_clean_html_removes_scripts_and_styles(self):
        """Удаление script и style тегов"""
        html = """
        <div>
            <script type="text/javascript">alert('test');</script>
            <p>Контент</p>
            <style>.hidden { display: none; }</style>
            <span>Еще контент</span>
        </div>
        """
        result = clean_html(html)
        assert "Контент" in result
        assert "Еще контент" in result
        assert "alert" not in result
        assert "display: none" not in result
    
    def test_clean_html_normalizes_whitespace(self):
        """Нормализация пробелов и переносов строк"""
        html = """
        <div>
            <p>   Много    пробелов   </p>
            
            
            <p>Несколько
            переносов</p>
        </div>
        """
        result = clean_html(html)
        # Не должно быть множественных пробелов
        assert "   " not in result
        # Должен быть нормализованный текст
        assert "Много пробелов" in result
        assert "Несколько переносов" in result
    
    def test_clean_html_empty_input(self):
        """Обработка пустого HTML"""
        assert clean_html("") == ""
        assert clean_html("   ") == ""
        assert clean_html(None) == ""
    
    def test_extract_visible_text(self):
        """Извлечение только видимого текста"""
        html = """
        <div>
            <p>Видимый текст</p>
            <div style="display: none;">Скрытый текст</div>
            <p class="hidden">Еще скрытый</p>
            <nav>Навигация</nav>
            <footer>Подвал</footer>
            <main>Основной контент</main>
        </div>
        """
        result = extract_visible_text(html)
        assert "Видимый текст" in result
        assert "Основной контент" in result
        assert "Скрытый текст" not in result
        # nav и footer должны быть удалены
        assert "Навигация" not in result
        assert "Подвал" not in result
    
    def test_remove_navigation_noise(self):
        """Удаление навигационного шума"""
        text = """
        Главная О нас Услуги Контакты
        Настоящий контент сайта
        © 2023 Все права защищены
        Cookie согласие принято
        Политика конфиденциальности
        """
        result = remove_navigation_noise(text)
        assert "Настоящий контент сайта" in result
        assert "Главная О нас Услуги Контакты" not in result
        assert "права защищены" not in result
        assert "Cookie" not in result
    
    def test_clean_html_malformed(self):
        """Обработка некорректного HTML"""
        html = "<div><p>Текст<unclosed><script>bad</script>Еще текст"
        result = clean_html(html)
        assert "Текст" in result
        assert "Еще текст" in result
        assert "bad" not in result