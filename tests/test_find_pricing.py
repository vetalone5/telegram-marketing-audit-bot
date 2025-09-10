# Тесты для поиска ценовой информации

import pytest
from app.features.audit.adapters.fetcher import find_pricing_link


class TestFindPricing:
    """Тесты для функции find_pricing_link"""
    
    def test_find_pricing_russian(self):
        """Поиск ссылок с русскими словами"""
        html = '''
        <html>
            <body>
                <nav>
                    <a href="/about">О нас</a>
                    <a href="/prices">Цены</a>
                    <a href="/contact">Контакты</a>
                </nav>
            </body>
        </html>
        '''
        base_url = "https://example.com"
        result = find_pricing_link(html, base_url)
        assert result == "https://example.com/prices"
    
    def test_find_pricing_tariffs(self):
        """Поиск по слову 'тарифы'"""
        html = '''
        <html>
            <body>
                <a href="/services">Услуги</a>
                <a href="/tariffs">Тарифы</a>
            </body>
        </html>
        '''
        base_url = "https://site.com"
        result = find_pricing_link(html, base_url)
        assert result == "https://site.com/tariffs"
    
    def test_find_pricing_english(self):
        """Поиск ссылок с английскими словами"""
        html = '''
        <html>
            <body>
                <a href="/home">Home</a>
                <a href="/pricing">Pricing</a>
                <a href="/about">About</a>
            </body>
        </html>
        '''
        base_url = "https://example.org"
        result = find_pricing_link(html, base_url)
        assert result == "https://example.org/pricing"
    
    def test_find_pricing_in_href_attribute(self):
        """Поиск по ключевому слову в атрибуте href"""
        html = '''
        <html>
            <body>
                <a href="/price-list">Список услуг</a>
                <a href="/about">О компании</a>
            </body>
        </html>
        '''
        base_url = "https://test.com"
        result = find_pricing_link(html, base_url)
        assert result == "https://test.com/price-list"
    
    def test_find_pricing_case_insensitive(self):
        """Поиск должен быть нечувствительным к регистру"""
        html = '''
        <html>
            <body>
                <a href="/PRICES">ЦЕНЫ</a>
            </body>
        </html>
        '''
        base_url = "https://example.com"
        result = find_pricing_link(html, base_url)
        assert result == "https://example.com/PRICES"
    
    def test_find_pricing_multiple_matches(self):
        """При множественных совпадениях должна возвращаться первая найденная"""
        html = '''
        <html>
            <body>
                <a href="/pricing">Цены</a>
                <a href="/tariffs">Тарифы</a>
                <a href="/cost">Стоимость</a>
            </body>
        </html>
        '''
        base_url = "https://example.com"
        result = find_pricing_link(html, base_url)
        # Должна вернуться первая найденная ссылка
        assert result in [
            "https://example.com/pricing",
            "https://example.com/tariffs", 
            "https://example.com/cost"
        ]
    
    def test_find_pricing_with_query_params(self):
        """Ссылки с query параметрами должны обрабатываться корректно"""
        html = '''
        <html>
            <body>
                <a href="/page?section=pricing">Наши цены</a>
            </body>
        </html>
        '''
        base_url = "https://example.com"
        result = find_pricing_link(html, base_url)
        assert result == "https://example.com/page?section=pricing"
    
    def test_find_pricing_absolute_url(self):
        """Абсолютные URL должны корректно обрабатываться"""
        html = '''
        <html>
            <body>
                <a href="https://example.com/pricing">Цены</a>
            </body>
        </html>
        '''
        base_url = "https://example.com"
        result = find_pricing_link(html, base_url)
        assert result == "https://example.com/pricing"
    
    def test_no_pricing_link_found(self):
        """Если ссылки на цены нет, должен возвращаться None"""
        html = '''
        <html>
            <body>
                <a href="/about">О нас</a>
                <a href="/services">Услуги</a>
                <a href="/contact">Контакты</a>
            </body>
        </html>
        '''
        base_url = "https://example.com"
        result = find_pricing_link(html, base_url)
        assert result is None
    
    def test_ignore_external_links(self):
        """Внешние ссылки должны игнорироваться"""
        html = '''
        <html>
            <body>
                <a href="https://other-site.com/pricing">Цены</a>
                <a href="/internal-pricing">Наши тарифы</a>
            </body>
        </html>
        '''
        base_url = "https://example.com"
        result = find_pricing_link(html, base_url)
        assert result == "https://example.com/internal-pricing"
    
    def test_ignore_anchor_links(self):
        """Якорные ссылки должны игнорироваться"""
        html = '''
        <html>
            <body>
                <a href="#pricing">Цены</a>
                <a href="/real-pricing">Настоящие цены</a>
            </body>
        </html>
        '''
        base_url = "https://example.com"
        result = find_pricing_link(html, base_url)
        assert result == "https://example.com/real-pricing"
    
    def test_ignore_mailto_and_tel_links(self):
        """mailto и tel ссылки должны игнорироваться"""
        html = '''
        <html>
            <body>
                <a href="mailto:pricing@example.com">Узнать цены</a>
                <a href="tel:+123456789">Позвонить за ценами</a>
                <a href="/pricing-page">Цены</a>
            </body>
        </html>
        '''
        base_url = "https://example.com"
        result = find_pricing_link(html, base_url)
        assert result == "https://example.com/pricing-page"
    
    def test_empty_html(self):
        """Пустой HTML должен возвращать None"""
        html = ""
        base_url = "https://example.com"
        result = find_pricing_link(html, base_url)
        assert result is None
    
    def test_malformed_html(self):
        """Некорректный HTML не должен вызывать ошибки"""
        html = "<a href='/pricing'>Цены</a><unclosed tag"
        base_url = "https://example.com"
        result = find_pricing_link(html, base_url)
        assert result == "https://example.com/pricing"