"""
Вспомогательные функции, утилиты форматирования, фильтры и экспортеры файлов.
"""

import csv
import io
import re
from datetime import datetime
from typing import Optional
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from bot.config import ADMIN_IDS
from bot.database.models import MailingLog


class IsAdminFilter(BaseFilter):
    """Фильтр для проверки, является ли пользователь администратором бота."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id if event.from_user else 0
        return user_id in ADMIN_IDS


def format_progress_bar(current: int, total: int, length: int = 10) -> str:
    """
    Генерирует визуальный прогресс-бар: [████░░░░░░] 40.0%
    """
    if total <= 0:
        return "[░░░░░░░░░░] 0%"
    percent = min(100.0, max(0.0, (current / total) * 100))
    filled_length = int(length * current // total)
    bar = "█" * filled_length + "░" * (length - filled_length)
    return f"[{bar}] {percent:.1f}%"


def clean_phone_number(phone: str) -> str:
    """Удаляет из номера телефона пробелы, дефисы, скобки, оставляя плюс и цифры."""
    phone = phone.strip()
    # Удаляем всё кроме + и цифр
    cleaned = re.sub(r"[^\d+]", "", phone)
    if not cleaned.startswith("+") and cleaned:
        cleaned = "+" + cleaned
    return cleaned


def normalize_telegram_target(target: str) -> str:
    """
    Нормализует ссылку или юзернейм группы:
    - https://t.me/groupname -> @groupname
    - t.me/groupname -> @groupname
    - https://t.me/+invite -> https://t.me/+invite
    - @groupname -> @groupname
    """
    target = target.strip()
    if not target:
        return ""
    
    # Если это приватная инвайт-ссылка
    if "t.me/+" in target or "t.me/joinchat/" in target:
        if not target.startswith("http"):
            target = "https://" + target
        return target

    # Если это публичная ссылка https://t.me/username
    match = re.search(r"(?:https?://)?(?:www\.)?t\.me/([a-zA-Z0-9_]+)", target)
    if match:
        return f"@{match.group(1)}"

    if not target.startswith("@") and not target.startswith("-") and not target.isdigit():
        return f"@{target}"

    return target


def export_logs_to_csv_file(logs: list[MailingLog]) -> BufferedInputFile:
    """Создает CSV-файл из записей журнала для отправки в Telegram."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["ID", "Mailing ID", "Телефон аккаунта", "Цель", "Название группы", "Статус", "Ошибка", "Время"])

    for log in logs:
        writer.writerow([
            log.id,
            log.mailing_id,
            log.account_phone,
            log.group_target,
            log.group_title,
            log.status,
            log.error_message or "",
            log.timestamp
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    filename = f"mailing_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return BufferedInputFile(file=csv_bytes, filename=filename)


def export_logs_to_txt_file(logs: list[MailingLog]) -> BufferedInputFile:
    """Создает текстовый файл отчета из записей журнала."""
    output = io.StringIO()
    output.write(f"=== ОТЧЕТ ПО РАССЫЛКЕ ОТ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} ===\n\n")

    for log in logs:
        status_icon = "✅" if log.status == "success" else "❌"
        err = f" | Ошибка: {log.error_message}" if log.error_message else ""
        output.write(
            f"[{log.timestamp}] {status_icon} [{log.status.upper()}] "
            f"Аккаунт: {log.account_phone} -> Группа: {log.group_title} ({log.group_target}){err}\n"
        )

    txt_bytes = output.getvalue().encode("utf-8")
    filename = f"mailing_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    return BufferedInputFile(file=txt_bytes, filename=filename)
