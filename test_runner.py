#!/usr/bin/env python3
"""
Простой скрипт для проверки основных функций перед запуском pytest
"""

import sys
import traceback

def test_imports():
    """Проверка импортов"""
    print("🔍 Проверяем импорты...")
    try:
        from app.core.utils import normalize_url
        print("✅ app.core.utils.normalize_url импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта app.core.utils.normalize_url: {e}")
        return False
    
    try:
        from app.features.audit.adapters.fetcher import find_pricing_link
        print("✅ app.features.audit.adapters.fetcher.find_pricing_link импортирован")
    except Exception as e:
        print(f"❌ Ошибка импорта app.features.audit.adapters.fetcher.find_pricing_link: {e}")
        return False
    
    return True

def test_normalize_url():
    """Быстрый тест normalize_url"""
    print("\n🔍 Тестируем normalize_url...")
    try:
        from app.core.utils import normalize_url
        
        # Базовые тесты
        test_cases = [
            ("site.com", "https://site.com"),
            ("  google.com  ", "https://google.com"),
            ("http://example.org", "https://example.org"),
            ("https://test.com", "https://test.com"),
        ]
        
        for input_val, expected in test_cases:
            result = normalize_url(input_val)
            if result == expected:
                print(f"✅ '{input_val}' -> '{result}'")
            else:
                print(f"❌ '{input_val}' -> '{result}' (ожидался '{expected}')")
                
    except Exception as e:
        print(f"❌ Ошибка в normalize_url: {e}")
        traceback.print_exc()

def test_find_pricing():
    """Быстрый тест find_pricing_link"""
    print("\n🔍 Тестируем find_pricing_link...")
    try:
        from app.features.audit.adapters.fetcher import find_pricing_link
        
        html = '''
        <html>
            <body>
                <a href="/about">О нас</a>
                <a href="/prices">Цены</a>
                <a href="/contact">Контакты</a>
            </body>
        </html>
        '''
        
        result = find_pricing_link(html, "https://example.com")
        expected = "https://example.com/prices"
        
        if result == expected:
            print(f"✅ Найдена ссылка на цены: {result}")
        else:
            print(f"❌ Результат: {result}, ожидался: {expected}")
            
    except Exception as e:
        print(f"❌ Ошибка в find_pricing_link: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Запускаем предварительную проверку...")
    
    if not test_imports():
        print("\n❌ Импорты не прошли, тесты не могут быть запущены")
        sys.exit(1)
    
    test_normalize_url()
    test_find_pricing()
    
    print("\n✅ Предварительная проверка завершена!")
    print("Теперь можно запустить: poetry run pytest tests/ -v")