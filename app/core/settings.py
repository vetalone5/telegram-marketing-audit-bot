from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram бот
    telegram_token: str = Field(..., description="Токен Telegram бота")
    
    # OpenAI API
    openai_api_key: str = Field(..., description="API ключ OpenAI")
    
    # Google Sheets
    google_sheets_id: str = Field(..., description="ID Google таблицы по умолчанию")
    google_service_json_path: str = Field(
        default="./secrets/service_account.json",
        description="Путь к JSON файлу с credentials Google API"
    )
    
    # Администраторы и лимиты
    admin_user_ids: str = Field(
        default="",
        description="Список ID администраторов через запятую"
    )
    default_user_limit: int = Field(
        default=10,
        description="Лимит запросов по умолчанию для пользователя"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    def get_admin_ids(self) -> List[int]:
        """Получение списка ID администраторов"""
        if not self.admin_user_ids.strip():
            return []
        return [int(x.strip()) for x in self.admin_user_ids.split(',') if x.strip()]

    def is_admin(self, user_id: int) -> bool:
        """Проверка является ли пользователь администратором"""
        return user_id in self.get_admin_ids()


# Глобальный экземпляр настроек
settings = Settings()