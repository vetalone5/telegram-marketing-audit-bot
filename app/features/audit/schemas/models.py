# Pydantic модели для данных

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class FullResult(BaseModel):
    """Полный результат анализа - все 27 колонок"""
    
    # Основные блоки
    offer_first_screen: str = Field(default="", description="Оффер (первый экран)")
    cta_first_screen: str = Field(default="", description="CTA (первый экран)")
    utp_formula: str = Field(default="", description="УТП (по формуле)")
    product_services: str = Field(default="", description="Продукт / услуги (кратко)")
    education_program: str = Field(default="", description="Программа обучения")
    all_cta: str = Field(default="", description="Все CTA (текст + контекст)")
    benefits: str = Field(default="", description="Выгоды")
    target_audience_pains: str = Field(default="", description="Боли ЦА")
    prices_tariffs: str = Field(default="", description="Цены и тарифы (с источником)")
    installment_payment: str = Field(default="", description="Рассрочка / Оплата позже")
    
    # Промо и доверие
    promotions: str = Field(default="", description="Акции (условия/сроки)")
    bonuses_gifts: str = Field(default="", description="Бонусы / Подарки")
    guarantees: str = Field(default="", description="Гарантии")
    trust_factors: str = Field(default="", description="Факторы доверия")
    lead_magnets: str = Field(default="", description="Лид-магниты / Квизы")
    
    # Контакты и формы
    contacts_social: str = Field(default="", description="Контакты и соцсети")
    online_chat: str = Field(default="", description="Онлайн-чат (наличие/тип/расположение)")
    application_forms: str = Field(default="", description="Формы заявки (поля/кнопки)")
    
    # Структура и контент
    main_structure: str = Field(default="", description="Структура главной (сверху вниз)")
    faq: str = Field(default="", description="FAQ (10–15 ключевых)")
    
    # Аналитика
    marketing_insights: str = Field(default="", description="Маркетинговые выводы")
    growth_hypotheses: str = Field(default="", description="Гипотезы роста (SMART)")
    brief_summary: str = Field(default="", description="Краткая сводка (3–4 пункта)")
    notes: str = Field(default="", description="Заметки (служебно)")

    @field_validator('target_audience_pains')
    @classmethod
    def validate_pains_count(cls, v):
        """Проверяем что болей ЦА минимум 7 пунктов"""
        if v and len(v.split('\n')) < 7:
            # Если меньше 7, не валидируем строго, но логируем
            pass
        return v


class ShortSummary(BaseModel):
    """Краткая сводка из 3-4 пунктов"""
    
    summary_points: List[str] = Field(
        description="Список из 3-4 ключевых пунктов анализа",
        min_length=3,
        max_length=4
    )


class RowForSheet(BaseModel):
    """Структура записи для Google Sheets"""
    
    # Метаданные
    timestamp: str = Field(description="Дата и время анализа")
    user_id: str = Field(description="ID пользователя")
    analyzed_url: str = Field(description="Анализируемый URL")
    pricing_url: Optional[str] = Field(default=None, description="URL страницы с ценами")
    
    # Все поля анализа (27 колонок)
    offer_first_screen: str = ""
    cta_first_screen: str = ""
    utp_formula: str = ""
    product_services: str = ""
    education_program: str = ""
    all_cta: str = ""
    benefits: str = ""
    target_audience_pains: str = ""
    prices_tariffs: str = ""
    installment_payment: str = ""
    promotions: str = ""
    bonuses_gifts: str = ""
    guarantees: str = ""
    trust_factors: str = ""
    lead_magnets: str = ""
    contacts_social: str = ""
    online_chat: str = ""
    application_forms: str = ""
    main_structure: str = ""
    faq: str = ""
    marketing_insights: str = ""
    growth_hypotheses: str = ""
    brief_summary: str = ""
    notes: str = ""
    
    @classmethod
    def from_full_result(
        cls, 
        result: FullResult, 
        user_id: str, 
        analyzed_url: str, 
        pricing_url: Optional[str] = None
    ) -> "RowForSheet":
        """Создание записи для таблицы из FullResult"""
        return cls(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id=user_id,
            analyzed_url=analyzed_url,
            pricing_url=pricing_url,
            **result.model_dump()
        )
    
    def to_sheet_row(self) -> List[str]:
        """Преобразование в список значений для записи в таблицу"""
        return [
            self.timestamp,
            self.user_id,
            self.analyzed_url,
            self.pricing_url or "",
            self.offer_first_screen,
            self.cta_first_screen,
            self.utp_formula,
            self.product_services,
            self.education_program,
            self.all_cta,
            self.benefits,
            self.target_audience_pains,
            self.prices_tariffs,
            self.installment_payment,
            self.promotions,
            self.bonuses_gifts,
            self.guarantees,
            self.trust_factors,
            self.lead_magnets,
            self.contacts_social,
            self.online_chat,
            self.application_forms,
            self.main_structure,
            self.faq,
            self.marketing_insights,
            self.growth_hypotheses,
            self.brief_summary,
            self.notes
        ]