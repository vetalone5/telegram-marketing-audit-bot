#!/usr/bin/env python3
"""
Функциональный тест Playwright с реальной веб-страницей
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_real_page_fetch():
    """Тест загрузки реальной веб-страницы"""
    try:
        from app.features.audit.adapters.playwright_fetcher import fetch_with_playwright, PLAYWRIGHT_AVAILABLE
        
        if not PLAYWRIGHT_AVAILABLE:
            print("⚠️  Playwright не доступен, пропускаем функциональный тест")
            return
            
        print("🌐 Тестируем загрузку реальной веб-страницы...")
        
        # Тестируем простую статическую страницу
        test_url = "https://httpbin.org/html"
        print(f"📡 Загружаем: {test_url}")
        
        result = await fetch_with_playwright(test_url)
        
        if result['success']:
            print("✅ Страница успешно загружена!")
            print(f"   - Заголовок: {result['title'][:50]}...")
            print(f"   - Статус: {result['status_code']}")
            print(f"   - Метод: {result['method']}")
            print(f"   - Размер контента: {len(result['content'])} символов")
            print(f"   - Найдено ссылок: {len(result.get('links', []))}")
            print(f"   - Найдено изображений: {len(result.get('images', []))}")
        else:
            print(f"❌ Ошибка загрузки: {result.get('error', 'Неизвестная ошибка')}")
            
    except Exception as e:
        print(f"❌ Ошибка функционального теста: {e}")

def main():
    """Главная функция теста"""
    print("🚀 Запуск функционального теста Playwright...")
    
    try:
        # Запускаем асинхронный тест
        asyncio.run(test_real_page_fetch())
        print("\n🎉 Функциональный тест завершен!")
        
    except KeyboardInterrupt:
        print("\n🛑 Тест прерван пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()