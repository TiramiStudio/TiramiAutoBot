"""
Модуль конфигурации бота.
Загружает переменные окружения из .env файла и валидирует основные настройки.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Базовая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# Токен Telegram-бота
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# Список ID администраторов (через запятую)
_admin_ids_raw: str = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
]

# Telegram API ID и Hash по умолчанию (my.telegram.org)
DEFAULT_API_ID: int = int(os.getenv("DEFAULT_API_ID", "0"))
DEFAULT_API_HASH: str = os.getenv("DEFAULT_API_HASH", "").strip()

# Пути к базам данных и сессиям
DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/bot.db")
SESSIONS_DIR: Path = BASE_DIR / os.getenv("SESSIONS_DIR", "sessions")
MEDIA_DIR: Path = BASE_DIR / os.getenv("MEDIA_DIR", "media")

# Автоматическое создание необходимых директорий
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def validate_config() -> None:
    """Проверяет корректность заполнения обязательных параметров конфигурации."""
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN не задан в .env файле!")
    if not ADMIN_IDS:
        errors.append("ADMIN_IDS не задан или не содержит корректных ID в .env файле!")
    
    if errors:
        raise ValueError("\n".join(errors))
