"""
Модели данных для работы с базой данных SQLite.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Account:
    """Модель Telegram-аккаунта (сессии Telethon)."""
    id: Optional[int] = None
    phone: str = ""
    session_name: str = ""
    api_id: int = 0
    api_hash: str = ""
    status: str = "active"  # active, flood_wait, banned, disabled, unauthorized
    flood_until: Optional[str] = None
    first_name: Optional[str] = None
    username: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used_at: Optional[str] = None


@dataclass
class Category:
    """Категория или тег для группировки целевых групп."""
    id: Optional[int] = None
    name: str = ""


@dataclass
class Group:
    """Целевая группа/канал для рассылки."""
    id: Optional[int] = None
    target: str = ""  # @username, https://t.me/+..., t.me/joinchat/..., или id
    title: str = ""
    category_id: Optional[int] = None
    status: str = "active"  # active, restricted, not_found, banned
    cooldown_seconds: int = 0  # 0 = использовать глобальные настройки задержки
    last_sent_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Template:
    """Шаблон сообщения для рассылки."""
    id: Optional[int] = None
    name: str = ""
    text: str = ""
    media_type: str = "text"  # text, photo, video, document, media_group
    media_files: str = "[]"  # JSON-список путей к файлам
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class MailingLog:
    """Запись в журнале рассылки."""
    id: Optional[int] = None
    mailing_id: str = ""
    account_phone: str = ""
    group_target: str = ""
    group_title: str = ""
    status: str = "success"  # success, flood_wait, error, restricted, not_found
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
