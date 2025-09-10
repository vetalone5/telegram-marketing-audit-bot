# Клавиатуры для Telegram бота
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def single_start_kb() -> InlineKeyboardMarkup:
    """Клавиатура с одной кнопкой 'Начать анализ'"""
    keyboard = [
        [InlineKeyboardButton("Начать анализ", callback_data="start_analysis")]
    ]
    return InlineKeyboardMarkup(keyboard)


def main_kb() -> InlineKeyboardMarkup:
    """Основная клавиатура с кнопками управления"""
    keyboard = [
        [InlineKeyboardButton("Новый анализ", callback_data="new_analysis")],
        [
            InlineKeyboardButton("Подключить таблицу", callback_data="connect_sheet"),
            InlineKeyboardButton("Открыть таблицу", callback_data="open_sheet")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def after_result_no_sheet_kb() -> InlineKeyboardMarkup:
    """Клавиатура после анализа без подключенной таблицы"""
    keyboard = [
        [InlineKeyboardButton("Подключить таблицу", callback_data="connect_sheet")],
        [InlineKeyboardButton("Новый анализ", callback_data="new_analysis")]
    ]
    return InlineKeyboardMarkup(keyboard)


def after_result_with_sheet_kb() -> InlineKeyboardMarkup:
    """Клавиатура после анализа с подключенной таблицей"""
    keyboard = [
        [InlineKeyboardButton("Открыть таблицу", callback_data="open_sheet")],
        [InlineKeyboardButton("Новый анализ", callback_data="new_analysis")]
    ]
    return InlineKeyboardMarkup(keyboard)