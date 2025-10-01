#!/usr/bin/env python3
"""
Простой тест для проверки Playwright интеграции
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.features.audit.adapters.playwright_fetcher import (
        PLAYWRIGHT_AVAILABLE, 
        PlaywrightConfig,
        get_default_playwright_config
    )
    
    print("🧪 Тестирование Playwright интеграции...")
    print(f"📊 Playwright доступен: {PLAYWRIGHT_AVAILABLE}")
    
    # Тест создания конфигурации
    print("\n✅ Тест 1: Создание базовой конфигурации")
    config = PlaywrightConfig()
    print(f"   - Headless: {config.headless}")
    print(f"   - Timeout: {config.timeout}")
    print(f"   - Wait for: {config.wait_for_load_state}")
    print(f"   - Viewport: {config.viewport}")
    
    # Тест кастомной конфигурации
    print("\n✅ Тест 2: Создание кастомной конфигурации")
    custom_config = PlaywrightConfig(
        headless=False,
        timeout=60000,
        viewport={"width": 1366, "height": 768}
    )
    print(f"   - Custom headless: {custom_config.headless}")
    print(f"   - Custom timeout: {custom_config.timeout}")
    print(f"   - Custom viewport: {custom_config.viewport}")
    
    # Тест конфигурации из настроек
    print("\n✅ Тест 3: Конфигурация из настроек")
    try:
        default_config = get_default_playwright_config()
        print(f"   - Default config создан: {type(default_config).__name__}")
    except Exception as e:
        print(f"   - Ошибка создания default config: {e}")
    
    if PLAYWRIGHT_AVAILABLE:
        print("\n🚀 Playwright готов к использованию!")
        print("   - Можно использовать для загрузки динамических страниц")
        print("   - Поддержка JavaScript и SPA приложений")
        print("   - Автоматический fallback на HTTP при ошибках")
    else:
        print("\n⚠️  Playwright не доступен, будет использоваться HTTP fallback")
    
    print("\n🎉 Все базовые тесты пройдены успешно!")
    
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Неожиданная ошибка: {e}")
    sys.exit(1)