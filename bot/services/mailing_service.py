"""
Сервис рассылки сообщений с поддержкой ротации аккаунтов, антибана,
динамического обновления прогресса, паузы/остановки и планировщика задач.
"""

import asyncio
import json
import logging
import random
import uuid
from datetime import datetime
from typing import Optional, Callable, Awaitable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telethon import errors

from bot.database.db import db
from bot.database.models import Account, Group, Template
from bot.services.telethon_manager import telethon_mgr
from bot.services.spintax import process_spintax
from bot.utils.helpers import format_progress_bar

logger = logging.getLogger(__name__)


class MailingService:
    """Менеджер процесса рассылки сообщений."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running: bool = False
        self.is_paused: bool = False
        self._stop_requested: bool = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # по умолчанию не на паузе

        self.current_mailing_id: Optional[str] = None
        self.total_targets: int = 0
        self.sent_count: int = 0
        self.error_count: int = 0
        self.current_target: str = ""
        self.current_account_phone: str = ""
        self.start_time: Optional[datetime] = None

        # Функция обратного вызова для обновления интерфейса бота (Telegram Message)
        self.ui_update_callback: Optional[Callable[[], Awaitable[None]]] = None
        self._last_ui_update: float = 0.0

    def start_scheduler(self) -> None:
        """Запуск планировщика задач APScheduler."""
        if not self.scheduler.running:
            self.scheduler.start()

    def get_progress_info(self) -> dict:
        """Возвращает текущую сводку о ходе выполнения рассылки."""
        elapsed = ""
        if self.start_time:
            seconds = int((datetime.now() - self.start_time).total_seconds())
            mins, secs = divmod(seconds, 60)
            elapsed = f"{mins}м {secs}с"

        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "mailing_id": self.current_mailing_id or "-",
            "total": self.total_targets,
            "sent": self.sent_count,
            "errors": self.error_count,
            "progress_bar": format_progress_bar(self.sent_count + self.error_count, self.total_targets),
            "current_target": self.current_target or "-",
            "current_account": self.current_account_phone or "-",
            "elapsed_time": elapsed or "-"
        }

    async def _notify_ui(self, force: bool = False) -> None:
        """Безопасное обновление статусного сообщения в Telegram с защитой от флуда."""
        if not self.ui_update_callback:
            return
        now = asyncio.get_event_loop().time()
        # Обновляем не чаще чем раз в 3 секунды, если не форсировано
        if force or (now - self._last_ui_update >= 3.0):
            self._last_ui_update = now
            try:
                await self.ui_update_callback()
            except Exception as e:
                logger.debug(f"Не удалось обновить статусное сообщение UI: {e}")

    def pause(self) -> None:
        """Ставит активную рассылку на паузу."""
        if self.is_running and not self.is_paused:
            self.is_paused = True
            self._pause_event.clear()

    def resume(self) -> None:
        """Возобновляет рассылку с паузы."""
        if self.is_running and self.is_paused:
            self.is_paused = False
            self._pause_event.set()

    def stop(self) -> None:
        """Останавливает активную рассылку."""
        if self.is_running:
            self._stop_requested = True
            self.is_paused = False
            self._pause_event.set()

    async def run_mailing(
        self,
        template_id: int,
        category_id: Optional[int] = None,
        ui_callback: Optional[Callable[[], Awaitable[None]]] = None
    ) -> None:
        """
        Основной цикл рассылки сообщений по группам.
        """
        if self.is_running:
            raise RuntimeError("Рассылка уже выполняется!")

        self.is_running = True
        self.is_paused = False
        self._stop_requested = False
        self._pause_event.set()
        self.current_mailing_id = str(uuid.uuid4())[:8]
        self.sent_count = 0
        self.error_count = 0
        self.start_time = datetime.now()
        self.ui_update_callback = ui_callback

        try:
            # Получаем шаблон
            template: Optional[Template] = await db.get_template_by_id(template_id)
            if not template:
                raise ValueError("Шаблон сообщения не найден!")

            # Получаем целевые группы
            groups: list[Group] = await db.get_groups(category_id=category_id, status="active")
            if not groups:
                raise ValueError("Список активных целевых групп пуст!")

            # Получаем активные аккаунты
            accounts: list[Account] = await db.get_accounts()
            active_accounts = [a for a in accounts if a.status == "active"]
            if not active_accounts:
                raise ValueError("Нет активных и авторизованных аккаунтов для рассылки!")

            self.total_targets = len(groups)
            await self._notify_ui(force=True)

            # Загружаем настройки задержек и лимитов
            settings = await db.get_all_settings()
            min_delay = float(settings.get("min_delay", "30"))
            max_delay = float(settings.get("max_delay", "90"))
            account_delay = float(settings.get("account_delay", "15"))
            daily_limit = int(settings.get("daily_limit_per_account", "50"))

            media_files = json.loads(template.media_files) if template.media_files else []
            account_index = 0

            for group in groups:
                # Проверка запроса на остановку
                if self._stop_requested:
                    logger.info("Рассылка остановлена пользователем.")
                    break

                # Ожидание, если стоит пауза
                await self._pause_event.wait()
                if self._stop_requested:
                    break

                self.current_target = f"{group.title} ({group.target})"
                await self._notify_ui()

                # Поиск подходящего аккаунта с учетом дневного лимита и статуса
                account: Optional[Account] = None
                attempts = 0
                while attempts < len(active_accounts):
                    candidate = active_accounts[account_index % len(active_accounts)]
                    account_index += 1
                    attempts += 1

                    # Проверяем суточный лимит
                    today_sent = await db.get_today_sent_count_for_account(candidate.phone)
                    if today_sent >= daily_limit:
                        continue

                    # Проверяем статус в БД
                    acc_fresh = await db.get_account_by_phone(candidate.phone)
                    if acc_fresh and acc_fresh.status == "active":
                        account = candidate
                        break

                if not account:
                    logger.warning("Все аккаунты исчерпали дневной лимит или заблокированы.")
                    break

                self.current_account_phone = account.phone
                await self._notify_ui()

                # Обрабатываем спинтакс для получения уникального текста
                personalized_text = process_spintax(template.text)

                # Попытка отправки сообщения
                try:
                    await telethon_mgr.send_message_to_target(
                        account=account,
                        target=group.target,
                        text=personalized_text,
                        media_type=template.media_type,
                        media_files=media_files
                    )
                    self.sent_count += 1
                    await db.update_account_last_used(account.phone)
                    await db.add_log(
                        mailing_id=self.current_mailing_id,
                        account_phone=account.phone,
                        group_target=group.target,
                        group_title=group.title,
                        status="success"
                    )
                except errors.FloodWaitError as e:
                    logger.warning(f"Флуд-бан на аккаунте {account.phone} на {e.seconds} сек.")
                    await db.update_account_status(account.phone, "flood_wait")
                    await db.add_log(
                        mailing_id=self.current_mailing_id,
                        account_phone=account.phone,
                        group_target=group.target,
                        group_title=group.title,
                        status="flood_wait",
                        error_message=f"Флуд-бан {e.seconds} сек."
                    )
                    self.error_count += 1
                except (errors.ChatWriteForbiddenError, errors.UserBannedInChannelError) as e:
                    logger.warning(f"Нет прав на отправку в группу {group.target}: {e}")
                    await db.update_group_status(group.target, "restricted")
                    await db.add_log(
                        mailing_id=self.current_mailing_id,
                        account_phone=account.phone,
                        group_target=group.target,
                        group_title=group.title,
                        status="restricted",
                        error_message="Запрещено писать / Бан в группе"
                    )
                    self.error_count += 1
                except (errors.ChannelPrivateError, errors.InviteHashExpiredError, ValueError) as e:
                    logger.warning(f"Группа {group.target} недоступна: {e}")
                    await db.update_group_status(group.target, "not_found")
                    await db.add_log(
                        mailing_id=self.current_mailing_id,
                        account_phone=account.phone,
                        group_target=group.target,
                        group_title=group.title,
                        status="not_found",
                        error_message=f"Не найдена / Недоступна: {str(e)}"
                    )
                    self.error_count += 1
                except Exception as e:
                    logger.error(f"Неизвестная ошибка при отправке в {group.target}: {e}")
                    await db.add_log(
                        mailing_id=self.current_mailing_id,
                        account_phone=account.phone,
                        group_target=group.target,
                        group_title=group.title,
                        status="error",
                        error_message=str(e)
                    )
                    self.error_count += 1

                await self._notify_ui()

                # Антибан-задержка между отправками
                sleep_duration = random.uniform(min_delay, max_delay)
                # Если доступно несколько аккаунтов, добавляем паузу переключения
                if len(active_accounts) > 1:
                    sleep_duration += account_delay

                await asyncio.sleep(sleep_duration)

        finally:
            self.is_running = False
            self.is_paused = False
            self._stop_requested = False
            self.current_target = ""
            self.current_account_phone = ""
            await self._notify_ui(force=True)

    def schedule_mailing(
        self,
        run_date: datetime,
        template_id: int,
        category_id: Optional[int] = None
    ) -> str:
        """Планирует отложенный запуск рассылки на указанную дату и время."""
        job_id = f"mailing_job_{uuid.uuid4().hex[:8]}"
        self.scheduler.add_job(
            self.run_mailing,
            "date",
            run_date=run_date,
            args=[template_id, category_id, None],
            id=job_id,
            replace_existing=True
        )
        return job_id


# Глобальный экземпляр сервиса рассылки
mailing_srv = MailingService()
