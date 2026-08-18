"""
Базовый роутер бота: обработка команды /start, главного меню, статистики и экспорта логов.
"""

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.database.db import db
from bot.keyboards.inline import main_menu_kb, stats_menu_kb, confirm_action_kb, about_kb
from bot.utils.helpers import IsAdminFilter, export_logs_to_csv_file, export_logs_to_txt_file

router = Router(name="common_router")
# Применяем фильтр администратора ко всем хэндлерам роутера
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start."""
    await state.clear()
    text = (
        "👋 <b>Добро пожаловать в панель управления TiramiAutoBot!</b>\n"
        "✨ <i>Разработано студией TiramiStudio</i>\n\n"
        "Выберите интересующий раздел в меню ниже:\n"
        "• <b>📱 Аккаунты</b> — привязка сессий Telethon, проверка статуса\n"
        "• <b>👥 Группы</b> — ручное добавление, автопарсинг диалогов, категории\n"
        "• <b>📝 Шаблоны</b> — настройка текстов, медиа, спинтакса и форматирования\n"
        "• <b>🚀 Рассылка</b> — запуск, пауза, остановка, планировщик\n"
        "• <b>⚙️ Настройки</b> — задержки между отправками, лимиты\n"
        "• <b>📊 Статистика</b> — сводка и экспорт журнала рассылок\n"
        "• <b>ℹ️ О студии</b> — контакты и социальные сети"
    )
    await message.answer(text, parse_mode="html", reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:about")
async def cb_about_menu(callback: CallbackQuery) -> None:
    """Отображение информации о разработчике и ссылок на соцсети."""
    text = (
        "🤖 <b>TiramiAutoBot</b> — профессиональный бот для автоматизации рассылок в Telegram\n\n"
        "👑 <b>Разработчик:</b> студия <b>TiramiStudio</b>\n\n"
        "🔗 <b>Наши официальные сообщества и ресурсы:</b>\n"
        "• 📢 <b>Telegram-канал:</b> <a href='https://t.me/tiramistudio'>t.me/tiramistudio</a>\n"
        "• 💬 <b>Discord-сообщество:</b> <a href='https://discord.gg/BcQEwxhT45'>discord.gg/BcQEwxhT45</a>\n\n"
        "Подписывайтесь, чтобы первыми получать обновления, новости и техническую поддержку!"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=about_kb(), disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат в главное меню из любого раздела."""
    await state.clear()
    text = (
        "🏠 <b>Главное меню управления рассылкой</b>\n\n"
        "Выберите раздел для продолжения работы:"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:stats")
async def cb_stats_menu(callback: CallbackQuery) -> None:
    """Отображение раздела статистики."""
    stats = await db.get_stats_summary()
    text = (
        "📊 <b>Общая статистика системы:</b>\n\n"
        f"📱 Аккаунтов подключено: <b>{stats['total_accounts']}</b> (активных: <b>{stats['active_accounts']}</b>)\n"
        f"👥 Целевых групп в базе: <b>{stats['total_groups']}</b>\n"
        f"📝 Создано шаблонов: <b>{stats['total_templates']}</b>\n\n"
        f"📤 Всего отправлено сообщений: <b>{stats['total_sent']}</b>\n"
        f"📅 Отправлено сегодня: <b>{stats['today_sent']}</b>\n"
        f"⚠️ Ошибок / Ограничений: <b>{stats['total_errors']}</b>\n\n"
        "Вы можете выгрузить детальный журнал рассылки в удобном формате:"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=stats_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "stats:export_txt")
async def cb_export_txt(callback: CallbackQuery) -> None:
    """Экспорт журнала рассылок в TXT файл."""
    logs = await db.get_logs(limit=500)
    if not logs:
        await callback.answer("Журнал рассылок пуст!", show_alert=True)
        return

    doc = export_logs_to_txt_file(logs)
    await callback.message.answer_document(
        document=doc,
        caption="📄 <b>Текстовый лог последних рассылок</b>",
        parse_mode="html"
    )
    await callback.answer("Лог сформирован и отправлен!")


@router.callback_query(F.data == "stats:export_csv")
async def cb_export_csv(callback: CallbackQuery) -> None:
    """Экспорт журнала рассылок в CSV файл."""
    logs = await db.get_logs(limit=500)
    if not logs:
        await callback.answer("Журнал рассылок пуст!", show_alert=True)
        return

    doc = export_logs_to_csv_file(logs)
    await callback.message.answer_document(
        document=doc,
        caption="📊 <b>CSV-таблица последних рассылок</b>",
        parse_mode="html"
    )
    await callback.answer("CSV сформирован и отправлен!")


@router.callback_query(F.data == "stats:clear_ask")
async def cb_clear_logs_ask(callback: CallbackQuery) -> None:
    """Запрос подтверждения очистки логов."""
    text = "⚠️ <b>Вы уверены, что хотите полностью очистить журнал рассылок?</b>"
    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=confirm_action_kb("stats:clear_confirm", "menu:stats")
    )
    await callback.answer()


@router.callback_query(F.data == "stats:clear_confirm")
async def cb_clear_logs_confirm(callback: CallbackQuery) -> None:
    """Очистка таблицы логов."""
    await db.clear_logs()
    await callback.answer("Журнал рассылок успешно очищен!", show_alert=True)
    await cb_stats_menu(callback)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    """Пустой обработчик для информационных кнопок."""
    await callback.answer()
