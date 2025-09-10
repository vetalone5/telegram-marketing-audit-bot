.PHONY: run logs lint test install clean

# Запуск бота
run:
	poetry run python -m app.telegram.bot

# Просмотр логов в реальном времени
logs:
	tail -f logs/bot.log

# Линтинг и форматирование
lint:
	poetry run ruff check .
	poetry run black --check .

# Автоисправление кода
format:
	poetry run ruff check --fix .
	poetry run black .

# Запуск тестов
test:
	poetry run pytest tests/ -v

# Установка зависимостей
install:
	poetry install

# Очистка кэша и временных файлов
clean:
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/

# Проверка всего (линт + тесты)
check: lint test

# Помощь
help:
	@echo "Доступные команды:"
	@echo "  run     - Запуск Telegram бота"
	@echo "  logs    - Просмотр логов в реальном времени"
	@echo "  lint    - Проверка кода (ruff + black)"
	@echo "  format  - Автоисправление кода"
	@echo "  test    - Запуск тестов"
	@echo "  install - Установка зависимостей"
	@echo "  clean   - Очистка временных файлов"
	@echo "  check   - Полная проверка (lint + test)"