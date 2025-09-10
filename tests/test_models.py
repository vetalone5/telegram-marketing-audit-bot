import pytest
from datetime import datetime
from app.features.audit.schemas.models import FullResult, RowForSheet


class TestPydanticModels:
    """Тесты для Pydantic моделей"""
    
    def test_full_result_creation(self):
        """Создание FullResult с валидными данными"""
        data = {
            "offer_first_screen": "Увеличим продажи в 2 раза",
            "cta_first_screen": "Получить консультацию",
            "utp_formula": "Единственная CRM для малого бизнеса",
            "product_services": "CRM система",
            "education_program": "",
            "all_cta": "Получить консультацию, Узнать цену, Попробовать бесплатно",
            "benefits": "Увеличение продаж\nАвтоматизация процессов",
            "target_audience_pains": "Потеря клиентов\nХаос в продажах\nНет учета",
            "prices_tariffs": "От 1000 руб/мес (главная)",
            "installment_payment": "Рассрочка 12 месяцев",
            "promotions": "Скидка 50% в первый месяц",
            "bonuses_gifts": "Бесплатная настройка",
            "guarantees": "Возврат денег 30 дней",
            "trust_factors": "5000+ клиентов, сертификаты",
            "lead_magnets": "Бесплатный аудит продаж",
            "contacts_social": "Телефон, email, Telegram",
            "online_chat": "Есть, правый нижний угол",
            "application_forms": "Имя, телефон, email",
            "main_structure": "Заголовок - Преимущества - Цены - Контакты",
            "faq": "Как подключить? Сколько стоит?",
            "marketing_insights": "Сильные УТП, слабые гарантии",
            "growth_hypotheses": "Добавить видео-отзывы",
            "brief_summary": "Хороший продукт\nНужно доработать цены",
            "notes": "Сайт загружается быстро"
        }
        
        result = FullResult(**data)
        assert result.offer_first_screen == "Увеличим продажи в 2 раза"
        assert result.cta_first_screen == "Получить консультацию"
        assert result.education_program == ""  # Пустое поле
    
    def test_full_result_empty_fields(self):
        """FullResult с пустыми полями"""
        result = FullResult()
        
        # Все поля должны быть пустыми строками по умолчанию
        assert result.offer_first_screen == ""
        assert result.cta_first_screen == ""
        assert result.utp_formula == ""
        assert result.notes == ""
    
    def test_full_result_dict_conversion(self):
        """Конвертация FullResult в словарь"""
        data = {
            "offer_first_screen": "Тестовый оффер",
            "utp_formula": "Тестовое УТП"
        }
        result = FullResult(**data)
        result_dict = result.model_dump()
        
        assert isinstance(result_dict, dict)
        assert result_dict["offer_first_screen"] == "Тестовый оффер"
        assert result_dict["utp_formula"] == "Тестовое УТП"
        # Остальные поля должны быть пустыми
        assert result_dict["education_program"] == ""
    
    def test_row_for_sheet_creation(self):
        """Создание RowForSheet"""
        row = RowForSheet(
            timestamp="2025-01-01 12:00:00",
            user_id="test_user",
            analyzed_url="https://example.com",
            pricing_url="https://example.com/pricing",
            offer_first_screen="Тестовый оффер"
        )
        
        assert row.user_id == "test_user"
        assert row.analyzed_url == "https://example.com"
        assert row.pricing_url == "https://example.com/pricing"
        assert row.offer_first_screen == "Тестовый оффер"
    
    def test_row_for_sheet_from_full_result(self):
        """Создание RowForSheet из FullResult"""
        full_result = FullResult(
            offer_first_screen="Тестовый оффер",
            cta_first_screen="Тестовый CTA",
            utp_formula="Тестовое УТП"
        )
        
        row = RowForSheet.from_full_result(
            result=full_result,
            user_id="test_user",
            analyzed_url="https://example.com",
            pricing_url="https://example.com/prices"
        )
        
        assert row.user_id == "test_user"
        assert row.analyzed_url == "https://example.com"
        assert row.pricing_url == "https://example.com/prices"
        assert row.offer_first_screen == "Тестовый оффер"
        assert row.cta_first_screen == "Тестовый CTA"
        assert row.utp_formula == "Тестовое УТП"
        # Проверяем что timestamp установлен
        assert row.timestamp != ""
    
    def test_row_for_sheet_to_list(self):
        """Конвертация RowForSheet в список для Google Sheets"""
        row = RowForSheet(
            timestamp="2025-01-01 12:00:00",
            user_id="test_user",
            analyzed_url="https://example.com",
            pricing_url="https://example.com/prices",
            offer_first_screen="Тестовый оффер",
            cta_first_screen="Тестовый CTA"
        )
        
        sheet_row = row.to_sheet_row()
        
        assert isinstance(sheet_row, list)
        assert len(sheet_row) == 28  # 4 метаданных + 24 поля анализа
        assert sheet_row[0] == "2025-01-01 12:00:00"  # timestamp
        assert sheet_row[1] == "test_user"  # user_id
        assert sheet_row[2] == "https://example.com"  # analyzed_url
        assert sheet_row[3] == "https://example.com/prices"  # pricing_url
        assert sheet_row[4] == "Тестовый оффер"  # offer_first_screen
        assert sheet_row[5] == "Тестовый CTA"  # cta_first_screen
    
    def test_target_audience_pains_validation(self):
        """Тестирование валидации болей ЦА"""
        # Меньше 7 пунктов - валидация должна пройти (просто предупреждение)
        pains = "Боль 1\nБоль 2\nБоль 3"
        result = FullResult(target_audience_pains=pains)
        assert result.target_audience_pains == pains
        
        # 7+ пунктов - нормально
        many_pains = "\n".join([f"Боль {i}" for i in range(1, 8)])
        result = FullResult(target_audience_pains=many_pains)
        assert result.target_audience_pains == many_pains