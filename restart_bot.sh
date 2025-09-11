#!/bin/bash

# 🤖 Скрипт для быстрого перезапуска локального Telegram бота с логами
# Использование: ./restart_bot.sh

set -e

echo "🛑 Останавливаем старые процессы бота..."

# Убиваем все процессы бота
pkill -f "app.telegram.bot" 2>/dev/null || echo "   ℹ️  Процессы бота не найдены"

# Ждем завершения процессов
sleep 2

echo "🗑️  Удаляем файл блокировки..."
rm -f /tmp/marketgaze_bot.lock

echo "🚀 Запускаем бота с логами в терминале..."
echo "   (для остановки нажмите Ctrl+C)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Экспортируем PATH для Poetry
export PATH="$HOME/.local/bin:$PATH"

# Запускаем бота БЕЗ фонового режима - логи будут в терминале
poetry run python -m app.telegram.bot