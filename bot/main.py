"""
=============================================================================
ИНСТРУКЦИЯ ПО УСТАНОВКЕ И ЗАПУСКУ БОТА АВТОРАССЫЛКИ
=============================================================================

1. Требования к окружению:
   - Python версии 3.10 или выше.
   - Аккаунты Telegram и токен бота от @BotFather.
   - API ID и API Hash (получить на https://my.telegram.org в разделе API development tools).

2. Установка зависимостей:
   Создайте и активируйте виртуальное окружение:
     python -m venv venv
     # На Windows:
     venv\\Scripts\\activate
     # На Linux/macOS:
     source venv/bin/activate

   Установите необходимые библиотеки:
     pip install -r requirements.txt

3. Настройка конфигурации:
   Скопируйте файл .env.example в .env:
     cp .env.example .env   (или вручную создайте файл .env)

   Заполните переменные:
     BOT_TOKEN=...          # Токен бота из @BotFather
     ADMIN_IDS=...          # Ваш числовой Telegram ID (узнать в @userinfobot)
     DEFAULT_API_ID=...     # API ID с my.telegram.org
     DEFAULT_API_HASH=...   # API Hash с my.telegram.org

4. Запуск бота:
   Запустите главный модуль из корневой директории проекта:
     python -m bot.main
   или:
     python bot/main.py
=============================================================================
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional
from aiohttp import web

# Добавляем корневую директорию проекта в sys.path для корректного импорта модулей
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BOT_TOKEN, validate_config
from bot.database.db import db
from bot.services.telethon_manager import telethon_mgr
from bot.services.mailing_service import mailing_srv

# Импорт роутеров
from bot.handlers.common import router as common_router
from bot.handlers.accounts import router as accounts_router
from bot.handlers.groups import router as groups_router
from bot.handlers.templates import router as templates_router
from bot.handlers.mailing import router as mailing_router
from bot.handlers.settings import router as settings_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("bot")

# Хранилище раннера веб-сервера для Render
render_web_runner: Optional[web.AppRunner] = None


async def start_render_health_server() -> Optional[web.AppRunner]:
    """
    Запуск легковесного HTTP-сервера для успешного прохождения
    проверки работоспособности (Health Check) сервиса на Render.
    """
    port_str = os.getenv("PORT")
    if not port_str:
        return None

    try:
        port = int(port_str)
    except ValueError:
        return None

    async def handle_ping(request: web.Request) -> web.Response:
        return web.Response(
            text="TiramiAutoBot is running and healthy!",
            content_type="text/plain"
        )

    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    app.router.add_get("/ping", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Render Health Check сервер успешно запущен на порту {port}")
    return runner


async def on_startup(bot: Bot) -> None:
    """Действия при запуске бота."""
    global render_web_runner

    logger.info("Инициализация базы данных SQLite...")
    await db.init_db()
    
    logger.info("Запуск планировщика задач APScheduler...")
    mailing_srv.start_scheduler()

    # Если бот развернут как Web Service на Render (передан PORT)
    render_web_runner = await start_render_health_server()
    
    bot_user = await bot.get_me()
    logger.info(f"Бот @{bot_user.username} успешно запущен и готов к работе!")


async def on_shutdown() -> None:
    """Действия при корректном завершении работы бота."""
    global render_web_runner

    logger.info("Завершение работы... Отключение всех сессий Telethon...")
    await telethon_mgr.disconnect_all()
    if mailing_srv.scheduler.running:
        mailing_srv.scheduler.shutdown(wait=False)

    if render_web_runner:
        await render_web_runner.cleanup()

    logger.info("Все соединения закрыты. Бот остановлен.")


async def main() -> None:
    """Главная точка входа в приложение."""
    # Валидация конфигурации
    try:
        validate_config()
    except ValueError as e:
        logger.critical(f"Ошибка конфигурации:\n{e}")
        return

    # Инициализация бота и диспетчера
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация хуков жизненного цикла
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Регистрация всех роутеров
    dp.include_router(common_router)
    dp.include_router(accounts_router)
    dp.include_router(groups_router)
    dp.include_router(templates_router)
    dp.include_router(mailing_router)
    dp.include_router(settings_router)

    # Пропуск накопившихся апдейтов и запуск long-polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
