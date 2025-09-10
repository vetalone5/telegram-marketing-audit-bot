from typing import Optional, Tuple, List, Dict, Any
import json
import re
import httpx
from openai import OpenAI
from loguru import logger

from app.core.settings import settings
from app.core.retry import retry_on_llm_error
from app.features.audit.schemas.models import FullResult
from app.features.audit.adapters.cleaner import clean_html

# Флаг для контроля использования web tools
USE_WEB_TOOLS = False  # По умолчанию отключен для стабильности


# System prompt для анализа маркетинговых лендингов
ANALYSIS_SYSTEM_PROMPT = """
Ты — аналитик маркетинговых лендингов. Твоя задача — извлечь информацию ТОЛЬКО из переданных текстов страниц и вернуть СТРОГИЙ JSON со строго заданными полями на русском языке.

Жёсткие правила:
1) Анализируй только явно видимый текст из входных данных (HOME_TEXT и PRICING_TEXT, если есть). Не додумывай факты, которых нет в тексте.
2) Если чего-то нет в тексте — заполни поле пустой строкой "" (не пиши "нет данных" и т.п.).
3) Для цен обязательно укажи источник: "главная" или "цены: <URL>" — если PRICING_TEXT дан и URL известен.
4) Боли ЦА — минимум 7 пунктов; допускается пометка [предп], если вывод логичен из текста.
5) FAQ — выбери 10–15 ключевых вопросов (и ответы, если видны).
6) "Структура главной" — перечисли блоки сверху вниз в формате: "Блок: [точный заголовок/описание] — [что содержит]".
7) Верни СТРОГО JSON без комментариев и без лишних полей. НИКАКИХ пояснений, кода, разметки — только JSON.

Список ключей JSON (все значения — строки; список пунктов допускается оформлять как многострочный текст с маркерами "- "):
- "Оффер (первый экран)"
- "CTA (первый экран)"
- "УТП (по формуле)"
- "Продукт / услуги (кратко)"
- "Программа обучения"
- "Все CTA (текст + контекст)"
- "Выгоды"
- "Боли ЦА"
- "Цены и тарифы (с источником)"
- "Рассрочка / Оплата позже"
- "Акции (условия/сроки)"
- "Бонусы / Подарки"
- "Гарантии"
- "Факторы доверия"
- "Лид-магниты / Квизы"
- "Контакты и соцсети"
- "Онлайн-чат (наличие/тип/расположение)"
- "Формы заявки (поля/кнопки)"
- "Структура главной (сверху вниз)"
- "FAQ (10–15 ключевых)"
- "Маркетинговые выводы"
- "Гипотезы роста (SMART)"
- "Краткая сводка (3–4 пункта)"
- "Заметки (служебно)"

Дополнительно:
- Если подозреваешь, что страница требует JS-рендеринга (мало контента или типичные признаки SPA), укажи это в "Заметки (служебно)" фразой: "Возможен JS-рендеринг".
- "Краткая сводка (3–4 пункта)" — сделай 3–4 ёмких маркерных тезиса о самом важном.
"""

# User prompt template для подстановки данных
ANALYSIS_USER_TEMPLATE = """
Дано две строки текста:
HOME_TEXT (главная страница):
---
{HOME_TEXT}
---

PRICING_TEXT (страница цен, если есть):
---
{PRICING_TEXT}
---

PRICING_URL (если есть): {PRICING_URL}

ЗАДАНИЕ:
Проанализируй только видимый текст. Верни СТРОГО JSON с ключами ровно из списка, без лишних полей и лишних пояснений.
Напомню, для "Цены и тарифы (с источником)" укажи источник: "главная" или "цены: {PRICING_URL}" (если PRICING_TEXT есть). 
"Боли ЦА" — минимум 7 пунктов (допускай [предп], если логично).
"FAQ (10–15 ключевых)" — не более 15.
"Краткая сводка (3–4 пункта)" — ровно 3–4 маркерных тезиса.

Верни только JSON.
"""


def clean_json_response(response_text: str) -> str:
    """
    Очистка ответа модели от лишних обёрток и извлечение JSON
    
    Args:
        response_text: Сырой ответ от модели
        
    Returns:
        Очищенная JSON строка
    """
    try:
        # Убираем тройные кавычки и маркдаун
        cleaned = re.sub(r'```json\s*', '', response_text)
        cleaned = re.sub(r'```\s*$', '', cleaned)
        cleaned = cleaned.strip()
        
        # Ищем первый JSON блок между фигурными скобками
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return cleaned
        
    except Exception as e:
        logger.warning(f"Ошибка очистки JSON ответа: {e}")
        return response_text


def parse_short_summary(summary_text: str) -> List[str]:
    """
    Парсинг краткой сводки в список пунктов
    
    Args:
        summary_text: Текст сводки
        
    Returns:
        Список пунктов (до 4 элементов)
    """
    if not summary_text:
        return []
    
    # Разбиваем по строкам и ищем маркеры
    lines = summary_text.split('\n')
    points = []
    
    for line in lines:
        line = line.strip()
        if line and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
            # Убираем маркер и добавляем пункт
            point = re.sub(r'^[-•*]\s*', '', line).strip()
            if point:
                points.append(point)
    
    # Если не нашли маркеры, пробуем разбить по точкам
    if not points and summary_text:
        sentences = [s.strip() for s in summary_text.split('.') if s.strip()]
        points = sentences
    
    # Ограничиваем до 4 пунктов
    return points[:4]


@retry_on_llm_error
async def analyze_content(
    home_text: str, 
    pricing_text: Optional[str] = None, 
    pricing_url: Optional[str] = None
) -> Tuple[FullResult, List[str]]:
    """
    Анализ контента сайта через GPT-4o
    
    Args:
        home_text: Текст главной страницы
        pricing_text: Текст страницы с ценами (опционально)
        pricing_url: URL страницы с ценами (опционально)
        
    Returns:
        Кортеж (FullResult, краткая сводка в виде списка)
    """
    try:
        logger.info(f"Начинаем анализ контента: {len(home_text)} символов главной, {len(pricing_text or '')} символов цен")
        
        # Создаем асинхронный клиент OpenAI
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Формируем пользовательский промпт
        user_content = ANALYSIS_USER_TEMPLATE.format(
            HOME_TEXT=home_text or "",
            PRICING_TEXT=pricing_text or "",
            PRICING_URL=pricing_url or ""
        )
        
        # Делаем асинхронный запрос к GPT-4o
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        # Логируем детали OpenAI запроса
        request_id = getattr(response, 'id', 'unknown')
        logger.info(f"OpenAI запрос ID: {request_id}")
        logger.debug(f"OpenAI модель: {response.model}")
        logger.debug(f"OpenAI usage: {response.usage}")
        
        # Извлекаем ответ
        raw_content = response.choices[0].message.content
        logger.debug(f"Получен ответ от GPT-4o: {len(raw_content)} символов")
        logger.debug(f"Полный ответ GPT-4o: {raw_content[:1000]}...")  # Первые 1000 символов для диагностики
        
        # Очищаем JSON от лишних обёрток
        cleaned_json = clean_json_response(raw_content)
        
        # Парсим JSON
        try:
            data = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            logger.error(f"Содержимое ответа: {cleaned_json[:500]}...")
            raise ValueError(f"GPT-4o вернул некорректный JSON: {e}")
        
        # Маппинг полей из русских ключей в поля модели
        field_mapping = {
            "Оффер (первый экран)": "offer_first_screen",
            "CTA (первый экран)": "cta_first_screen", 
            "УТП (по формуле)": "utp_formula",
            "Продукт / услуги (кратко)": "product_services",
            "Программа обучения": "education_program",
            "Все CTA (текст + контекст)": "all_cta",
            "Выгоды": "benefits",
            "Боли ЦА": "target_audience_pains",
            "Цены и тарифы (с источником)": "prices_tariffs",
            "Рассрочка / Оплата позже": "installment_payment",
            "Акции (условия/сроки)": "promotions",
            "Бонусы / Подарки": "bonuses_gifts",
            "Гарантии": "guarantees",
            "Факторы доверия": "trust_factors",
            "Лид-магниты / Квизы": "lead_magnets",
            "Контакты и соцсети": "contacts_social",
            "Онлайн-чат (наличие/тип/расположение)": "online_chat",
            "Формы заявки (поля/кнопки)": "application_forms",
            "Структура главной (сверху вниз)": "main_structure",
            "FAQ (10–15 ключевых)": "faq",
            "Маркетинговые выводы": "marketing_insights",
            "Гипотезы роста (SMART)": "growth_hypotheses",
            "Краткая сводка (3–4 пункта)": "brief_summary",
            "Заметки (служебно)": "notes"
        }
        
        # Преобразуем данные для FullResult, подставляем "" для отсутствующих полей
        result_data = {}
        for json_field, model_field in field_mapping.items():
            result_data[model_field] = data.get(json_field, "")
        
        # Создаем FullResult
        full_result = FullResult(**result_data)
        
        # Извлекаем краткую сводку
        brief_summary_text = data.get("Краткая сводка (3–4 пункта)", "")
        short_summary = parse_short_summary(brief_summary_text)
        
        # Если сводки нет, создаем fallback
        if not short_summary:
            short_summary = [
                result_data.get("offer_first_screen", "Анализ завершен")[:100],
                result_data.get("product_services", "Данные извлечены")[:100],
                result_data.get("marketing_insights", "Рекомендации подготовлены")[:100]
            ]
            short_summary = [s for s in short_summary if s][:4]
        
        logger.info("Анализ GPT-4o завершен успешно")
        return full_result, short_summary
        
    except Exception as e:
        logger.error(f"Ошибка анализа GPT-4o: {e}")
        raise


async def fetch_url(url: str) -> Dict[str, str]:
    """
    Локальная реализация tool для загрузки URL
    
    Args:
        url: URL для загрузки
        
    Returns:
        Словарь с данными: {"url", "html", "text"}
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            
            html_content = response.text
            text_content = clean_html(html_content)
            
            logger.debug(f"Tool fetch_url: {url} -> {len(text_content)} символов")
            
            return {
                "url": url,
                "html": html_content[:10000],  # Ограничиваем размер
                "text": text_content[:8000]     # Ограничиваем размер для GPT
            }
            
    except Exception as e:
        logger.error(f"Ошибка tool fetch_url для {url}: {e}")
        return {"url": url, "html": "", "text": f"Ошибка загрузки: {str(e)}"}


async def web_search(query: str) -> Dict[str, List[Dict]]:
    """
    Заглушка для web_search tool (пока не реализован)
    
    Args:
        query: Поисковый запрос
        
    Returns:
        Словарь с пустыми результатами
    """
    logger.debug(f"Tool web_search вызван с запросом: {query}")
    return {"results": []}


# Определение доступных tools для GPT
AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Загрузка содержимого веб-страницы по URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL страницы для загрузки"}
                },
                "required": ["url"]
            }
        }
    }
]

# Маппинг функций tools
TOOL_FUNCTIONS = {
    "fetch_url": fetch_url,
    "web_search": web_search
}


@retry_on_llm_error
async def run_with_tools(messages: List[Dict[str, str]]) -> str:
    """
    Выполнение диалога с GPT-4o с поддержкой function calling
    
    Args:
        messages: Список сообщений для диалога
        
    Returns:
        Финальный текстовый ответ от модели
    """
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        current_messages = messages.copy()
        max_iterations = 5  # Защита от бесконечных циклов
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"Tool цикл, итерация {iteration}")
            
            # Определяем tools в зависимости от флага
            tools = AVAILABLE_TOOLS if USE_WEB_TOOLS else None
            
            # Делаем запрос к GPT-4o
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=current_messages,
                tools=tools,
                tool_choice="auto" if tools else None,
                temperature=0.3,
                max_tokens=4000
            )
            
            message = response.choices[0].message
            
            # Если нет tool calls, возвращаем финальный ответ
            if not message.tool_calls:
                logger.debug(f"Tool цикл завершен за {iteration} итераций")
                return message.content
            
            # Добавляем ответ модели в историю
            current_messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [tc.model_dump() for tc in message.tool_calls]
            })
            
            # Выполняем каждый tool call
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Выполняем tool: {function_name} с аргументами: {function_args}")
                
                if function_name in TOOL_FUNCTIONS:
                    try:
                        # Вызываем функцию
                        if function_name == "fetch_url":
                            result = await TOOL_FUNCTIONS[function_name](function_args["url"])
                        else:
                            result = await TOOL_FUNCTIONS[function_name](**function_args)
                        
                        result_content = json.dumps(result, ensure_ascii=False)
                        logger.debug(f"Tool {function_name} выполнен успешно")
                        
                    except Exception as tool_error:
                        result_content = json.dumps({
                            "error": f"Ошибка выполнения {function_name}: {str(tool_error)}"
                        }, ensure_ascii=False)
                        logger.error(f"Ошибка tool {function_name}: {tool_error}")
                else:
                    result_content = json.dumps({
                        "error": f"Неизвестная функция: {function_name}"
                    }, ensure_ascii=False)
                    logger.error(f"Неизвестный tool: {function_name}")
                
                # Добавляем результат tool в историю
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": result_content
                })
        
        # Если достигли максимума итераций
        logger.warning(f"Tool цикл достиг максимума итераций ({max_iterations})")
        return "Анализ прерван: слишком много обращений к инструментам"
        
    except Exception as e:
        logger.error(f"Ошибка в tool цикле: {e}")
        raise