import pytest
from app.core.utils import normalize_url


class TestUrlNormalize:
    """Тесты для функции normalize_url"""
    
    def test_simple_domain(self):
        """Простой домен должен получить https схему"""
        assert normalize_url("site.com") == "https://site.com"
        assert normalize_url("google.com") == "https://google.com"
        assert normalize_url("example.org") == "https://example.org"
    
    def test_www_removal(self):
        """www должен удаляться"""
        assert normalize_url("www.site.com") == "https://site.com"
        assert normalize_url("https://www.google.com") == "https://google.com"
        assert normalize_url("http://www.example.org") == "https://example.org"
    
    def test_http_to_https(self):
        """http должен заменяться на https"""
        assert normalize_url("http://site.com") == "https://site.com"
        assert normalize_url("http://example.org/page") == "https://example.org/page"
    
    def test_https_preserved(self):
        """https должен сохраняться"""
        assert normalize_url("https://site.com") == "https://site.com"
        assert normalize_url("https://example.org/page") == "https://example.org/page"
    
    def test_whitespace_trimmed(self):
        """Пробелы должны обрезаться"""
        assert normalize_url("  site.com  ") == "https://site.com"
        assert normalize_url("\t google.com \n") == "https://google.com"
        assert normalize_url("   https://example.org   ") == "https://example.org"
    
    def test_trailing_slash_removed(self):
        """Trailing slash должен удаляться для корневого пути"""
        assert normalize_url("site.com/") == "https://site.com"
        assert normalize_url("https://example.org/") == "https://example.org"
    
    def test_path_preserved(self):
        """Пути должны сохраняться"""
        assert normalize_url("site.com/about") == "https://site.com/about"
        assert normalize_url("example.org/products/item") == "https://example.org/products/item"
    
    def test_query_params_preserved(self):
        """Query параметры должны сохраняться"""
        assert normalize_url("site.com?param=value") == "https://site.com?param=value"
        assert normalize_url("example.org/page?id=123&type=test") == "https://example.org/page?id=123&type=test"
    
    def test_complex_url(self):
        """Комплексный тест с множественными преобразованиями"""
        input_url = "  http://www.site.com/page?param=value  "
        expected = "https://site.com/page?param=value"
        assert normalize_url(input_url) == expected
    
    def test_empty_and_invalid_inputs(self):
        """Пустые и некорректные входные данные"""
        assert normalize_url("") == ""
        assert normalize_url("   ") == ""
        assert normalize_url(None) == ""
    
    def test_case_insensitive_domain(self):
        """Домены должны быть в нижнем регистре"""
        assert normalize_url("SITE.COM") == "https://site.com"
        assert normalize_url("Example.ORG") == "https://example.org"
        assert normalize_url("https://WWW.GOOGLE.COM") == "https://google.com"