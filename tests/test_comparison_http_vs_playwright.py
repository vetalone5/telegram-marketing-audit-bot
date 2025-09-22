#!/usr/bin/env python3
"""
Сравнительный тест HTTP vs Playwright методов
Тестируем на реальном сайте https://m-sistema.ru/
"""
import sys
import os
import asyncio
import time
import json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def compare_methods(url: str):
    """Сравнительный тест двух методов загрузки"""
    
    print(f"🔄 Сравнительный тест для: {url}")
    print("=" * 80)
    
    # Импортируем необходимые модули
    try:
        from app.features.audit.adapters.fetcher import get_content_bundle_http
        from app.features.audit.adapters.playwright_fetcher import fetch_with_playwright, PLAYWRIGHT_AVAILABLE
        
        results = {}
        
        # ============================================
        # ТЕСТ 1: HTTP метод (старый)
        # ============================================
        print("\n🌐 ТЕСТ 1: HTTP метод (старый)")
        print("-" * 40)
        
        start_time = time.time()
        try:
            http_result = await get_content_bundle_http(url)
            http_time = time.time() - start_time
            
            home_text = http_result.get('home_text', '')
            pricing_text = http_result.get('pricing_text', '')
            pricing_url = http_result.get('pricing_url', '')
            requires_js = http_result.get('requires_js', False)
            
            print(f"✅ HTTP метод выполнен за {http_time:.2f} секунд")
            print(f"📄 Размер главной страницы: {len(home_text)} символов")
            print(f"💰 Найдена страница цен: {'Да' if pricing_url else 'Нет'}")
            if pricing_url:
                print(f"   URL цен: {pricing_url}")
                print(f"   Размер страницы цен: {len(pricing_text)} символов")
            print(f"⚠️  Требует JavaScript: {'Да' if requires_js else 'Нет'}")
            
            # Анализируем контент
            home_words = len(home_text.split()) if home_text else 0
            pricing_words = len(pricing_text.split()) if pricing_text else 0
            
            print(f"📊 Количество слов на главной: {home_words}")
            if pricing_words > 0:
                print(f"📊 Количество слов на странице цен: {pricing_words}")
            
            # Проверяем наличие ключевых элементов
            has_navigation = any(word in home_text.lower() for word in ['меню', 'навигация', 'главная', 'о компании'])
            has_content = home_words > 100
            has_contacts = any(word in home_text.lower() for word in ['телефон', 'email', 'контакт', '+7', '@'])
            
            print(f"🔍 Обнаружена навигация: {'Да' if has_navigation else 'Нет'}")
            print(f"📝 Достаточно контента: {'Да' if has_content else 'Нет'}")
            print(f"📞 Найдены контакты: {'Да' if has_contacts else 'Нет'}")
            
            results['http'] = {
                'success': True,
                'time': http_time,
                'home_text_length': len(home_text),
                'home_words': home_words,
                'pricing_found': bool(pricing_url),
                'pricing_text_length': len(pricing_text),
                'pricing_words': pricing_words,
                'requires_js': requires_js,
                'has_navigation': has_navigation,
                'has_content': has_content,
                'has_contacts': has_contacts,
                'pricing_url': pricing_url
            }
            
        except Exception as e:
            http_time = time.time() - start_time
            print(f"❌ HTTP метод не сработал: {e}")
            results['http'] = {
                'success': False,
                'time': http_time,
                'error': str(e)
            }
        
        # ============================================
        # ТЕСТ 2: Playwright метод (новый)
        # ============================================
        print(f"\n🎭 ТЕСТ 2: Playwright метод (новый)")
        print("-" * 40)
        
        if not PLAYWRIGHT_AVAILABLE:
            print("❌ Playwright не доступен, тест пропущен")
            results['playwright'] = {
                'success': False,
                'error': 'Playwright не установлен'
            }
        else:
            start_time = time.time()
            try:
                playwright_result = await fetch_with_playwright(url)
                playwright_time = time.time() - start_time
                
                if playwright_result.get('success'):
                    title = playwright_result.get('title', '')
                    content = playwright_result.get('content', '')
                    meta_description = playwright_result.get('meta_description', '')
                    meta_keywords = playwright_result.get('meta_keywords', '')
                    links = playwright_result.get('links', [])
                    images = playwright_result.get('images', [])
                    status_code = playwright_result.get('status_code', 0)
                    
                    print(f"✅ Playwright метод выполнен за {playwright_time:.2f} секунд")
                    print(f"📄 Заголовок страницы: {title[:60]}{'...' if len(title) > 60 else ''}")
                    print(f"📄 Размер HTML контента: {len(content)} символов")
                    print(f"📊 HTTP статус: {status_code}")
                    print(f"🔗 Найдено ссылок: {len(links)}")
                    print(f"🖼️  Найдено изображений: {len(images)}")
                    
                    if meta_description:
                        print(f"📝 Meta description: {meta_description[:100]}{'...' if len(meta_description) > 100 else ''}")
                    if meta_keywords:
                        print(f"🏷️  Meta keywords: {meta_keywords}")
                    
                    # Извлекаем текст из HTML
                    from bs4 import BeautifulSoup
                    try:
                        soup = BeautifulSoup(content, 'html.parser')
                        # Удаляем скрипты и стили
                        for script in soup(["script", "style"]):
                            script.decompose()
                        text_content = soup.get_text()
                        # Очищаем от лишних пробелов
                        lines = (line.strip() for line in text_content.splitlines())
                        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                        clean_text = ' '.join(chunk for chunk in chunks if chunk)
                        
                        words_count = len(clean_text.split())
                        print(f"📊 Количество слов в тексте: {words_count}")
                        
                        # Ищем ссылки на цены в найденных ссылках
                        pricing_links = []
                        pricing_keywords = ['цены', 'цена', 'тариф', 'тарифы', 'стоимость', 'прайс', 'pricing', 'price']
                        
                        for link in links:
                            link_text = link.get('text', '').lower()
                            link_href = link.get('href', '').lower()
                            if any(keyword in link_text or keyword in link_href for keyword in pricing_keywords):
                                pricing_links.append(link)
                        
                        print(f"💰 Найдено ссылок на цены: {len(pricing_links)}")
                        for plink in pricing_links[:3]:  # Показываем первые 3
                            print(f"   - {plink.get('text', 'Без текста')}: {plink.get('href', '')}")
                        
                        # Анализ качества контента
                        has_navigation_pw = any(word in clean_text.lower() for word in ['меню', 'навигация', 'главная', 'о компании', 'услуги', 'продукт'])
                        has_content_pw = words_count > 100
                        has_contacts_pw = any(word in clean_text.lower() for word in ['телефон', 'email', 'контакт', '+7', '@', 'связь'])
                        
                        print(f"🔍 Обнаружена навигация: {'Да' if has_navigation_pw else 'Нет'}")
                        print(f"📝 Достаточно контента: {'Да' if has_content_pw else 'Нет'}")
                        print(f"📞 Найдены контакты: {'Да' if has_contacts_pw else 'Нет'}")
                        
                        results['playwright'] = {
                            'success': True,
                            'time': playwright_time,
                            'title': title,
                            'content_length': len(content),
                            'text_length': len(clean_text),
                            'words_count': words_count,
                            'status_code': status_code,
                            'links_count': len(links),
                            'images_count': len(images),
                            'pricing_links_count': len(pricing_links),
                            'meta_description': meta_description,
                            'meta_keywords': meta_keywords,
                            'has_navigation': has_navigation_pw,
                            'has_content': has_content_pw,
                            'has_contacts': has_contacts_pw,
                            'pricing_links': pricing_links[:3]  # Первые 3 ссылки
                        }
                        
                    except ImportError:
                        print("⚠️  BeautifulSoup не установлен, анализ текста пропущен")
                        results['playwright'] = {
                            'success': True,
                            'time': playwright_time,
                            'content_length': len(content),
                            'links_count': len(links),
                            'images_count': len(images)
                        }
                        
                else:
                    print(f"❌ Playwright не смог загрузить страницу: {playwright_result.get('error', 'Неизвестная ошибка')}")
                    results['playwright'] = {
                        'success': False,
                        'time': playwright_time,
                        'error': playwright_result.get('error', 'Неизвестная ошибка')
                    }
                    
            except Exception as e:
                playwright_time = time.time() - start_time
                print(f"❌ Playwright метод не сработал: {e}")
                results['playwright'] = {
                    'success': False,
                    'time': playwright_time,
                    'error': str(e)
                }
        
        # ============================================
        # СРАВНИТЕЛЬНЫЙ АНАЛИЗ
        # ============================================
        print(f"\n📊 СРАВНИТЕЛЬНЫЙ АНАЛИЗ")
        print("=" * 80)
        
        if results.get('http', {}).get('success') and results.get('playwright', {}).get('success'):
            http_data = results['http']
            pw_data = results['playwright']
            
            print(f"⏱️  Время выполнения:")
            print(f"   HTTP: {http_data['time']:.2f} сек")
            print(f"   Playwright: {pw_data['time']:.2f} сек")
            if pw_data['time'] > http_data['time']:
                print(f"   🐌 Playwright медленнее на {pw_data['time'] - http_data['time']:.2f} сек")
            else:
                print(f"   🚀 Playwright быстрее на {http_data['time'] - pw_data['time']:.2f} сек")
            
            print(f"\n📄 Количество контента:")
            print(f"   HTTP: {http_data['home_words']} слов")
            print(f"   Playwright: {pw_data.get('words_count', 0)} слов")
            
            content_diff = pw_data.get('words_count', 0) - http_data['home_words']
            if content_diff > 0:
                print(f"   📈 Playwright извлек на {content_diff} слов больше (+{content_diff/http_data['home_words']*100:.1f}%)")
            elif content_diff < 0:
                print(f"   📉 HTTP извлек на {abs(content_diff)} слов больше")
            else:
                print(f"   ⚖️  Одинаковое количество слов")
            
            print(f"\n🔍 Качество извлечения:")
            print(f"   HTTP - Навигация: {'✅' if http_data['has_navigation'] else '❌'}, Контент: {'✅' if http_data['has_content'] else '❌'}, Контакты: {'✅' if http_data['has_contacts'] else '❌'}")
            print(f"   Playwright - Навигация: {'✅' if pw_data['has_navigation'] else '❌'}, Контент: {'✅' if pw_data['has_content'] else '❌'}, Контакты: {'✅' if pw_data['has_contacts'] else '❌'}")
            
            print(f"\n💰 Поиск цен:")
            print(f"   HTTP: {'✅ Найдена страница цен' if http_data['pricing_found'] else '❌ Не найдено'}")
            print(f"   Playwright: {'✅ Найдено ' + str(pw_data.get('pricing_links_count', 0)) + ' ссылок на цены' if pw_data.get('pricing_links_count', 0) > 0 else '❌ Не найдено'}")
            
            print(f"\n🎯 Рекомендация:")
            
            # Логика рекомендации
            pw_score = 0
            http_score = 0
            
            # Очки за количество контента
            if pw_data.get('words_count', 0) > http_data['home_words']:
                pw_score += 2
            elif http_data['home_words'] > pw_data.get('words_count', 0):
                http_score += 1
            
            # Очки за поиск цен
            if pw_data.get('pricing_links_count', 0) > 0:
                pw_score += 2
            if http_data['pricing_found']:
                http_score += 2
            
            # Очки за качество извлечения
            if pw_data['has_content'] and pw_data['has_contacts']:
                pw_score += 1
            if http_data['has_content'] and http_data['has_contacts']:
                http_score += 1
            
            # Штраф за время (если Playwright слишком медленный)
            if pw_data['time'] > http_data['time'] * 3:
                pw_score -= 1
            
            if pw_score > http_score:
                print(f"   🎭 Рекомендуется использовать Playwright (Score: {pw_score} vs {http_score})")
                print(f"   💡 Playwright лучше извлекает динамический контент")
            elif http_score > pw_score:
                print(f"   🌐 Рекомендуется использовать HTTP (Score: {http_score} vs {pw_score})")
                print(f"   💡 HTTP быстрее и достаточно эффективен для этого сайта")
            else:
                print(f"   ⚖️  Оба метода показали похожие результаты (Score: {pw_score} vs {http_score})")
                print(f"   💡 Можно использовать HTTP для скорости или Playwright для надежности")
                
        elif results.get('http', {}).get('success'):
            print("✅ Работает только HTTP метод")
            print("💡 Playwright имеет проблемы, используйте HTTP fallback")
            
        elif results.get('playwright', {}).get('success'):
            print("✅ Работает только Playwright метод") 
            print("💡 HTTP не справляется, Playwright обязателен для этого сайта")
            
        else:
            print("❌ Оба метода не сработали")
            print("💡 Возможны проблемы с доступностью сайта или сетью")
        
        # Сохраняем результаты в файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"comparison_results_{timestamp}.json"
        
        full_results = {
            'url': url,
            'timestamp': timestamp,
            'results': results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(full_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Результаты сохранены в: {filename}")
        
        return results
        
    except Exception as e:
        print(f"❌ Критическая ошибка сравнительного теста: {e}")
        return None

def main():
    """Главная функция"""
    test_url = "https://skyeng.ru/"
    
    print("🧪 СРАВНИТЕЛЬНЫЙ ТЕСТ: HTTP vs Playwright")
    print(f"🌐 Тестируемый сайт: {test_url}")
    print(f"📅 Дата тестирования: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        results = asyncio.run(compare_methods(test_url))
        
        if results:
            print(f"\n🎉 Сравнительный тест завершен успешно!")
        else:
            print(f"\n❌ Тест не удался")
            
    except KeyboardInterrupt:
        print(f"\n🛑 Тест прерван пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")

if __name__ == "__main__":
    main()