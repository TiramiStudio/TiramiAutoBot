"""
Асинхронная работа с базой данных SQLite через aiosqlite.
Содержит функции инициализации схемы и методы выборки/сохранения данных.
"""

import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Any, AsyncGenerator
import aiosqlite

from bot.config import DATABASE_PATH
from bot.database.models import Account, Category, Group, Template, MailingLog


class Database:
    """Класс для взаимодействия с базой данных SQLite."""

    def __init__(self, db_path: str = str(DATABASE_PATH)):
        self.db_path = db_path

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Контекстный менеджер безопасного асинхронного соединения с базой данных."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    async def init_db(self) -> None:
        """Инициализация таблиц базы данных и установка начальных настроек."""
        async with self.get_connection() as db:
            # Таблица аккаунтов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT UNIQUE NOT NULL,
                    session_name TEXT UNIQUE NOT NULL,
                    api_id INTEGER NOT NULL,
                    api_hash TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    flood_until TEXT,
                    first_name TEXT,
                    username TEXT,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT
                )
            """)

            # Таблица категорий
            await db.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)

            # Таблица целевых групп
            await db.execute("""
                CREATE TABLE IF NOT EXISTS groups_list (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    category_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
                )
            """)

            # Таблица шаблонов сообщений
            await db.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    text TEXT NOT NULL,
                    media_type TEXT NOT NULL DEFAULT 'text',
                    media_files TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
            """)

            # Таблица глобальных настроек
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Таблица журнала рассылок
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mailing_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mailing_id TEXT NOT NULL,
                    account_phone TEXT NOT NULL,
                    group_target TEXT NOT NULL,
                    group_title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    timestamp TEXT NOT NULL
                )
            """)

            # Начальные настройки по умолчанию
            default_settings = {
                "min_delay": "30",
                "max_delay": "90",
                "account_delay": "15",
                "daily_limit_per_account": "50",
                "rotation_mode": "round_robin"
            }
            for key, value in default_settings.items():
                await db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value)
                )

            await db.commit()

    # ==========================================
    # Методы для работы с аккаунтами
    # ==========================================

    async def add_account(
        self,
        phone: str,
        session_name: str,
        api_id: int,
        api_hash: str,
        first_name: Optional[str] = None,
        username: Optional[str] = None
    ) -> int:
        """Добавляет новый аккаунт или обновляет существующий."""
        now = datetime.now().isoformat()
        async with self.get_connection() as db:
            cursor = await db.execute("""
                INSERT INTO accounts (phone, session_name, api_id, api_hash, first_name, username, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                ON CONFLICT(phone) DO UPDATE SET
                    session_name=excluded.session_name,
                    api_id=excluded.api_id,
                    api_hash=excluded.api_hash,
                    first_name=excluded.first_name,
                    username=excluded.username,
                    status='active',
                    flood_until=NULL
            """, (phone, session_name, api_id, api_hash, first_name, username, now))
            await db.commit()
            return cursor.lastrowid or 0

    async def get_accounts(self) -> list[Account]:
        """Получает список всех аккаунтов."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM accounts ORDER BY id ASC")
            rows = await cursor.fetchall()
            return [Account(**dict(row)) for row in rows]

    async def get_account_by_id(self, account_id: int) -> Optional[Account]:
        """Получает аккаунт по ID."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
            row = await cursor.fetchone()
            return Account(**dict(row)) if row else None

    async def get_account_by_phone(self, phone: str) -> Optional[Account]:
        """Получает аккаунт по номеру телефона."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM accounts WHERE phone = ?", (phone,))
            row = await cursor.fetchone()
            return Account(**dict(row)) if row else None

    async def update_account_status(
        self,
        phone: str,
        status: str,
        flood_until: Optional[str] = None
    ) -> None:
        """Обновляет статус аккаунта и время истечения флуд-бана при наличии."""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE accounts SET status = ?, flood_until = ? WHERE phone = ?",
                (status, flood_until, phone)
            )
            await db.commit()

    async def update_account_info(
        self,
        phone: str,
        first_name: Optional[str],
        username: Optional[str]
    ) -> None:
        """Обновляет имя и username аккаунта."""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE accounts SET first_name = ?, username = ? WHERE phone = ?",
                (first_name, username, phone)
            )
            await db.commit()

    async def update_account_last_used(self, phone: str) -> None:
        """Обновляет дату последнего использования аккаунта."""
        now = datetime.now().isoformat()
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE accounts SET last_used_at = ? WHERE phone = ?",
                (now, phone)
            )
            await db.commit()

    async def delete_account(self, account_id: int) -> Optional[str]:
        """Удаляет аккаунт и возвращает имя сессии для удаления файла."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT session_name FROM accounts WHERE id = ?", (account_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            session_name = row["session_name"]
            await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            await db.commit()
            return session_name

    # ==========================================
    # Методы для работы с категориями
    # ==========================================

    async def add_category(self, name: str) -> int:
        """Создает новую категорию."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "INSERT INTO categories (name) VALUES (?) ON CONFLICT(name) DO NOTHING",
                (name.strip(),)
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def get_categories(self) -> list[Category]:
        """Возвращает все категории."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM categories ORDER BY name ASC")
            rows = await cursor.fetchall()
            return [Category(**dict(row)) for row in rows]

    async def get_category_by_id(self, category_id: int) -> Optional[Category]:
        """Получает категорию по ID."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
            row = await cursor.fetchone()
            return Category(**dict(row)) if row else None

    async def delete_category(self, category_id: int) -> None:
        """Удаляет категорию (в группах category_id станет NULL)."""
        async with self.get_connection() as db:
            await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            await db.commit()

    # ==========================================
    # Методы для работы с группами
    # ==========================================

    async def add_group(
        self,
        target: str,
        title: str,
        category_id: Optional[int] = None
    ) -> bool:
        """Добавляет новую группу. Возвращает True если добавлена, False если уже есть."""
        now = datetime.now().isoformat()
        async with self.get_connection() as db:
            try:
                await db.execute("""
                    INSERT INTO groups_list (target, title, category_id, status, created_at)
                    VALUES (?, ?, ?, 'active', ?)
                    ON CONFLICT(target) DO UPDATE SET
                        title=excluded.title,
                        category_id=COALESCE(excluded.category_id, groups_list.category_id),
                        status='active'
                """, (target.strip(), title.strip(), category_id, now))
                await db.commit()
                return True
            except Exception:
                return False

    async def add_groups_bulk(
        self,
        groups: list[dict[str, Any]],
        category_id: Optional[int] = None
    ) -> int:
        """Массовое добавление групп. Возвращает количество успешно добавленных/обновленных групп."""
        now = datetime.now().isoformat()
        count = 0
        async with self.get_connection() as db:
            for g in groups:
                target = g.get("target", "").strip()
                title = g.get("title", target).strip()
                if not target:
                    continue
                await db.execute("""
                    INSERT INTO groups_list (target, title, category_id, status, created_at)
                    VALUES (?, ?, ?, 'active', ?)
                    ON CONFLICT(target) DO UPDATE SET
                        title=excluded.title,
                        category_id=COALESCE(excluded.category_id, groups_list.category_id),
                        status='active'
                """, (target, title, category_id, now))
                count += 1
            await db.commit()
        return count

    async def get_groups(
        self,
        category_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> list[Group]:
        """Возвращает список целевых групп с возможностью фильтрации по категории и статусу."""
        query = "SELECT * FROM groups_list WHERE 1=1"
        params = []
        if category_id is not None:
            query += " AND category_id = ?"
            params.append(category_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id DESC"

        async with self.get_connection() as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [Group(**dict(row)) for row in rows]

    async def get_group_by_id(self, group_id: int) -> Optional[Group]:
        """Получает группу по ID."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM groups_list WHERE id = ?", (group_id,))
            row = await cursor.fetchone()
            return Group(**dict(row)) if row else None

    async def update_group_status(self, target: str, status: str) -> None:
        """Обновляет статус группы (active, restricted, not_found, banned)."""
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE groups_list SET status = ? WHERE target = ?",
                (status, target)
            )
            await db.commit()

    async def delete_group(self, group_id: int) -> None:
        """Удаляет группу по ID."""
        async with self.get_connection() as db:
            await db.execute("DELETE FROM groups_list WHERE id = ?", (group_id,))
            await db.commit()

    async def clear_all_groups(self) -> None:
        """Удаляет все группы из базы."""
        async with self.get_connection() as db:
            await db.execute("DELETE FROM groups_list")
            await db.commit()

    async def count_groups(self, category_id: Optional[int] = None) -> int:
        """Возвращает общее количество групп."""
        query = "SELECT COUNT(*) as cnt FROM groups_list WHERE 1=1"
        params = []
        if category_id is not None:
            query += " AND category_id = ?"
            params.append(category_id)
        async with self.get_connection() as db:
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            return row["cnt"] if row else 0

    # ==========================================
    # Методы для работы с шаблонами
    # ==========================================

    async def add_template(
        self,
        name: str,
        text: str,
        media_type: str = "text",
        media_files: list[str] = None
    ) -> int:
        """Создает новый шаблон сообщения."""
        now = datetime.now().isoformat()
        media_json = json.dumps(media_files or [])
        async with self.get_connection() as db:
            cursor = await db.execute("""
                INSERT INTO templates (name, text, media_type, media_files, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    text=excluded.text,
                    media_type=excluded.media_type,
                    media_files=excluded.media_files
            """, (name.strip(), text, media_type, media_json, now))
            await db.commit()
            return cursor.lastrowid or 0

    async def get_templates(self) -> list[Template]:
        """Возвращает все сохраненные шаблоны."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM templates ORDER BY id DESC")
            rows = await cursor.fetchall()
            return [Template(**dict(row)) for row in rows]

    async def get_template_by_id(self, template_id: int) -> Optional[Template]:
        """Получает шаблон по ID."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
            row = await cursor.fetchone()
            return Template(**dict(row)) if row else None

    async def delete_template(self, template_id: int) -> None:
        """Удаляет шаблон."""
        async with self.get_connection() as db:
            await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
            await db.commit()

    # ==========================================
    # Методы для работы с настройками
    # ==========================================

    async def get_setting(self, key: str, default: str = "") -> str:
        """Получает значение настройки по ключу."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        """Сохраняет значение настройки."""
        async with self.get_connection() as db:
            await db.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (key, str(value)))
            await db.commit()

    async def get_all_settings(self) -> dict[str, str]:
        """Возвращает словарь всех настроек."""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT key, value FROM settings")
            rows = await cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}

    # ==========================================
    # Методы для журнала и статистики
    # ==========================================

    async def add_log(
        self,
        mailing_id: str,
        account_phone: str,
        group_target: str,
        group_title: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Добавляет запись в журнал рассылки."""
        now = datetime.now().isoformat()
        async with self.get_connection() as db:
            await db.execute("""
                INSERT INTO mailing_logs (mailing_id, account_phone, group_target, group_title, status, error_message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (mailing_id, account_phone, group_target, group_title, status, error_message, now))
            await db.commit()

    async def get_logs(self, limit: int = 200) -> list[MailingLog]:
        """Получает последние записи журнала."""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM mailing_logs ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [MailingLog(**dict(row)) for row in rows]

    async def get_today_sent_count_for_account(self, phone: str) -> int:
        """Подсчитывает количество успешных отправок с аккаунта за текущие сутки."""
        today_start = datetime.now().strftime("%Y-%m-%d") + "T00:00:00"
        async with self.get_connection() as db:
            cursor = await db.execute("""
                SELECT COUNT(*) as cnt FROM mailing_logs
                WHERE account_phone = ? AND status = 'success' AND timestamp >= ?
            """, (phone, today_start))
            row = await cursor.fetchone()
            return row["cnt"] if row else 0

    async def get_stats_summary(self) -> dict[str, int]:
        """Возвращает сводную статистику по боту."""
        async with self.get_connection() as db:
            acc_cur = await db.execute("SELECT COUNT(*) as cnt FROM accounts")
            total_accounts = (await acc_cur.fetchone())["cnt"]

            active_acc_cur = await db.execute("SELECT COUNT(*) as cnt FROM accounts WHERE status = 'active'")
            active_accounts = (await active_acc_cur.fetchone())["cnt"]

            grp_cur = await db.execute("SELECT COUNT(*) as cnt FROM groups_list")
            total_groups = (await grp_cur.fetchone())["cnt"]

            tmpl_cur = await db.execute("SELECT COUNT(*) as cnt FROM templates")
            total_templates = (await tmpl_cur.fetchone())["cnt"]

            log_sent_cur = await db.execute("SELECT COUNT(*) as cnt FROM mailing_logs WHERE status = 'success'")
            total_sent = (await log_sent_cur.fetchone())["cnt"]

            log_err_cur = await db.execute("SELECT COUNT(*) as cnt FROM mailing_logs WHERE status != 'success'")
            total_errors = (await log_err_cur.fetchone())["cnt"]

            today_start = datetime.now().strftime("%Y-%m-%d") + "T00:00:00"
            today_sent_cur = await db.execute(
                "SELECT COUNT(*) as cnt FROM mailing_logs WHERE status = 'success' AND timestamp >= ?",
                (today_start,)
            )
            today_sent = (await today_sent_cur.fetchone())["cnt"]

            return {
                "total_accounts": total_accounts,
                "active_accounts": active_accounts,
                "total_groups": total_groups,
                "total_templates": total_templates,
                "total_sent": total_sent,
                "total_errors": total_errors,
                "today_sent": today_sent
            }

    async def clear_logs(self) -> None:
        """Очищает историю журнала рассылки."""
        async with self.get_connection() as db:
            await db.execute("DELETE FROM mailing_logs")
            await db.commit()


# Глобальный экземпляр базы данных
db = Database()
