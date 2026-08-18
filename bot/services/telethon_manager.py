"""
Сервис для управления Telethon-клиентами, авторизации, парсинга диалогов и отправки сообщений.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Any
from telethon import TelegramClient, errors, functions
from telethon.tl.types import Channel, Chat, User

from bot.config import SESSIONS_DIR, DEFAULT_API_ID, DEFAULT_API_HASH
from bot.database.models import Account
from bot.database.db import db

logger = logging.getLogger(__name__)


class TelethonManager:
    """Менеджер для работы с сессиями и клиентами Telethon."""

    def __init__(self):
        # Хранилище активных клиентов: {phone: TelegramClient}
        self.clients: dict[str, TelegramClient] = {}
        # Временное хранилище данных авторизации в процессе: {phone: dict}
        self.pending_auth: dict[str, dict[str, Any]] = {}

    def get_session_path(self, session_name: str) -> str:
        """Возвращает полный путь к файлу сессии."""
        return str(SESSIONS_DIR / session_name)

    async def get_client(self, account: Account) -> TelegramClient:
        """Получает или создает и подключает клиент для переданного аккаунта."""
        phone = account.phone
        if phone in self.clients and self.clients[phone].is_connected():
            return self.clients[phone]

        api_id = account.api_id or DEFAULT_API_ID
        api_hash = account.api_hash or DEFAULT_API_HASH
        session_path = self.get_session_path(account.session_name)

        client = TelegramClient(
            session_path,
            api_id,
            api_hash,
            device_model="Desktop",
            system_version="Windows 11",
            app_version="5.4.1 x64",
            lang_code="ru",
            system_lang_code="ru"
        )
        await client.connect()
        self.clients[phone] = client
        return client

    async def disconnect_all(self) -> None:
        """Отключает все активные клиенты при завершении работы бота."""
        for phone, client in list(self.clients.items()):
            try:
                if client.is_connected():
                    await client.disconnect()
            except Exception as e:
                logger.error(f"Ошибка при отключении клиента {phone}: {e}")
        self.clients.clear()

    # ==========================================
    # Авторизация аккаунтов (Phone -> Code -> 2FA)
    # ==========================================

    async def request_code(
        self,
        phone: str,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Инициирует отправку кода подтверждения на указанный номер телефона.
        """
        api_id = api_id or DEFAULT_API_ID
        api_hash = api_hash or DEFAULT_API_HASH
        session_name = f"acc_{phone.replace('+', '').replace(' ', '')}"
        session_path = self.get_session_path(session_name)

        client = TelegramClient(
            session_path,
            api_id,
            api_hash,
            device_model="Desktop",
            system_version="Windows 11",
            app_version="5.4.1 x64",
            lang_code="ru",
            system_lang_code="ru"
        )
        await client.connect()

        try:
            sent_code = await client.send_code_request(phone)
            self.pending_auth[phone] = {
                "client": client,
                "phone_code_hash": sent_code.phone_code_hash,
                "api_id": api_id,
                "api_hash": api_hash,
                "session_name": session_name
            }
            return {
                "success": True,
                "phone_code_hash": sent_code.phone_code_hash,
                "session_name": session_name
            }
        except errors.FloodWaitError as e:
            await client.disconnect()
            return {"success": False, "error": f"Флуд-бан! Подождите {e.seconds} сек."}
        except Exception as e:
            await client.disconnect()
            return {"success": False, "error": str(e)}

    async def submit_code(self, phone: str, code: str) -> dict[str, Any]:
        """
        Отправляет полученный код подтверждения в Telegram.
        """
        auth_data = self.pending_auth.get(phone)
        if not auth_data:
            return {"success": False, "error": "Сессия авторизации не найдена. Начните заново."}

        client: TelegramClient = auth_data["client"]
        phone_code_hash = auth_data["phone_code_hash"]

        try:
            user = await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            # Успешная авторизация без 2FA
            await db.add_account(
                phone=phone,
                session_name=auth_data["session_name"],
                api_id=auth_data["api_id"],
                api_hash=auth_data["api_hash"],
                first_name=user.first_name,
                username=user.username
            )
            self.clients[phone] = client
            del self.pending_auth[phone]
            return {"success": True, "needs_2fa": False, "user": user}
        except errors.SessionPasswordNeededError:
            # Требуется пароль двухфакторной аутентификации (2FA)
            return {"success": True, "needs_2fa": True}
        except errors.PhoneCodeInvalidError:
            return {"success": False, "error": "Неверный код подтверждения! Проверьте и попробуйте снова."}
        except errors.PhoneCodeExpiredError:
            await self.cancel_pending_auth(phone)
            return {"success": False, "error": "Срок действия кода истек. Начните заново."}
        except errors.FloodWaitError as e:
            return {"success": False, "error": f"Слишком много попыток. Подождите {e.seconds} сек."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def submit_password(self, phone: str, password: str) -> dict[str, Any]:
        """
        Завершает авторизацию вводом пароля 2FA.
        """
        auth_data = self.pending_auth.get(phone)
        if not auth_data:
            return {"success": False, "error": "Сессия авторизации не найдена. Начните заново."}

        client: TelegramClient = auth_data["client"]

        try:
            user = await client.sign_in(password=password)
            await db.add_account(
                phone=phone,
                session_name=auth_data["session_name"],
                api_id=auth_data["api_id"],
                api_hash=auth_data["api_hash"],
                first_name=user.first_name,
                username=user.username
            )
            self.clients[phone] = client
            del self.pending_auth[phone]
            return {"success": True, "user": user}
        except errors.PasswordHashInvalidError:
            return {"success": False, "error": "Неверный пароль 2FA! Попробуйте еще раз."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def cancel_pending_auth(self, phone: str) -> None:
        """Отменяет начатую процедуру авторизации и освобождает ресурсы."""
        if phone in self.pending_auth:
            client: TelegramClient = self.pending_auth[phone].get("client")
            if client and client.is_connected():
                try:
                    await client.disconnect()
                except Exception:
                    pass
            del self.pending_auth[phone]

    # ==========================================
    # Проверка статуса аккаунта
    # ==========================================

    async def check_account_status(self, account: Account) -> dict[str, Any]:
        """
        Проверяет валидность сессии аккаунта и обновляет информацию в базе.
        """
        try:
            client = await self.get_client(account)
            if not await client.is_user_authorized():
                await db.update_account_status(account.phone, "unauthorized")
                return {"status": "unauthorized", "message": "Не авторизован"}

            me: User = await client.get_me()
            await db.update_account_info(account.phone, me.first_name, me.username)
            await db.update_account_status(account.phone, "active")
            return {
                "status": "active",
                "first_name": me.first_name or "",
                "username": me.username or "",
                "id": me.id
            }
        except errors.UserDeactivatedError:
            await db.update_account_status(account.phone, "banned")
            return {"status": "banned", "message": "Аккаунт удален или заблокирован Telegram"}
        except errors.AuthKeyUnregisteredError:
            await db.update_account_status(account.phone, "unauthorized")
            return {"status": "unauthorized", "message": "Ключ авторизации сброшен"}
        except errors.FloodWaitError as e:
            await db.update_account_status(account.phone, "flood_wait")
            return {"status": "flood_wait", "message": f"Флуд-бан на {e.seconds} сек."}
        except Exception as e:
            logger.error(f"Ошибка проверки статуса аккаунта {account.phone}: {e}")
            return {"status": "error", "message": str(e)}

    # ==========================================
    # Автопарсинг групп аккаунта
    # ==========================================

    async def parse_account_dialogs(self, account: Account) -> list[dict[str, str]]:
        """
        Парсит все группы и супергруппы, в которых состоит аккаунт.
        """
        client = await self.get_client(account)
        if not await client.is_user_authorized():
            raise RuntimeError(f"Аккаунт {account.phone} не авторизован")

        groups = []
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, (Chat, Channel)):
                # Исключаем широковещательные каналы без права писать (только мегагруппы/супергруппы или чаты)
                if isinstance(entity, Channel) and entity.broadcast and not entity.megagroup:
                    continue

                if entity.username:
                    target = f"@{entity.username}"
                else:
                    target = str(dialog.id)

                title = dialog.name or "Без названия"
                groups.append({"target": target, "title": title})

        return groups

    # ==========================================
    # Отправка сообщений в целевую группу
    # ==========================================

    async def send_message_to_target(
        self,
        account: Account,
        target: str,
        text: str,
        media_type: str = "text",
        media_files: Optional[list[str]] = None
    ) -> None:
        """
        Отправляет сообщение (текст/медиа/альбом) в указанную группу.
        """
        client = await self.get_client(account)
        if not await client.is_user_authorized():
            raise RuntimeError(f"Аккаунт {account.phone} не авторизован")

        entity = None
        # Обработка инвайт-ссылок
        if "t.me/+" in target or "t.me/joinchat/" in target:
            invite_hash = target.split("+")[-1].split("/")[-1]
            try:
                # Пытаемся вступить по инвайт-ссылке
                updates = await client(functions.messages.ImportChatInviteRequest(invite_hash))
                if updates.chats:
                    entity = updates.chats[0]
            except errors.UserAlreadyParticipantError:
                # Уже участник, ищем в диалогах или через get_entity
                entity = await client.get_entity(target)
            except Exception as e:
                # Если не удалось вступить, пробуем прямо получить сущность
                entity = await client.get_entity(target)
        else:
            entity = await client.get_entity(target)

        # Отправка в зависимости от типа контента
        if media_type == "text" or not media_files:
            await client.send_message(entity, text, parse_mode="html")
        elif media_type in ["photo", "video", "document"]:
            file_path = media_files[0]
            if os.path.exists(file_path):
                await client.send_file(
                    entity,
                    file_path,
                    caption=text,
                    parse_mode="html"
                )
            else:
                # Если локальный файл не найден, отправляем просто текст
                await client.send_message(entity, text, parse_mode="html")
        elif media_type == "media_group":
            # Проверяем существование локальных файлов
            existing_files = [f for f in media_files if os.path.exists(f)]
            if existing_files:
                await client.send_file(
                    entity,
                    existing_files,
                    caption=text,
                    parse_mode="html"
                )
            else:
                await client.send_message(entity, text, parse_mode="html")


# Глобальный экземпляр менеджера Telethon
telethon_mgr = TelethonManager()
