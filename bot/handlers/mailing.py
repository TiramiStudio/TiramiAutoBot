"""
Роутер для управления рассылкой: пошаговый мастер запуска, подтверждение,
живой мониторинг прогресса, пауза, остановка и планирование по времени (APScheduler).
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.database.db import db
from bot.database.models import Template, Category, Account
from bot.keyboards.inline import (
    mailing_menu_kb,
    select_template_for_mail_kb,
    select_category_for_mail_kb,
    custom_back_kb,
    confirm_action_kb
)
from bot.services.mailing_service import mailing_srv
from bot.utils.helpers import IsAdminFilter
from bot.utils.states import MailingStates

router = Router(name="mailing_router")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())

# Хранилище chat_id и message_id для динамического обновления карточки прогресса
active_monitor_msg: dict[str, int] = {}


def build_status_text(progress: dict) -> str:
    """Форматирует текст активного мониторинга рассылки."""
    state_icon = "⏸ <b>НА ПАУЗЕ</b>" if progress["is_paused"] else ("🚀 <b>В ПРОЦЕССЕ</b>" if progress["is_running"] else "🏁 <b>ЗАВЕРШЕНА</b>")

    return (
        f"📊 <b>Панель управления рассылкой</b>\n\n"
        f"Статус: {state_icon}\n"
        f"ID рассылки: <code>{progress['mailing_id']}</code>\n"
        f"Прогресс: <b>{progress['sent'] + progress['errors']} / {progress['total']}</b>\n"
        f"{progress['progress_bar']}\n\n"
        f"✅ Успешно отправлено: <b>{progress['sent']}</b>\n"
        f"⚠️ Ошибок / Ограничений: <b>{progress['errors']}</b>\n"
        f"📱 Текущий аккаунт: <code>{progress['current_account']}</code>\n"
        f"🎯 Текущая цель: <code>{progress['current_target']}</code>\n"
        f"⏱ Прошло времени: <b>{progress['elapsed_time']}</b>"
    )


async def update_monitor_ui(bot: Bot) -> None:
    """Функция обновления мониторинга, вызываемая из MailingService."""
    chat_id = active_monitor_msg.get("chat_id")
    message_id = active_monitor_msg.get("message_id")
    if not chat_id or not message_id:
        return

    progress = mailing_srv.get_progress_info()
    text = build_status_text(progress)
    kb = mailing_menu_kb(is_running=progress["is_running"], is_paused=progress["is_paused"])

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="html",
            reply_markup=kb
        )
    except Exception:
        pass


@router.callback_query(F.data == "menu:mailing")
async def cb_mailing_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Главный экран раздела Рассылка."""
    await state.clear()

    if mailing_srv.is_running:
        active_monitor_msg["chat_id"] = callback.message.chat.id
        active_monitor_msg["message_id"] = callback.message.message_id
        progress = mailing_srv.get_progress_info()
        text = build_status_text(progress)
        kb = mailing_menu_kb(is_running=True, is_paused=mailing_srv.is_paused)
    else:
        text = (
            "🚀 <b>Центр управления авторассылкой</b>\n\n"
            "Здесь вы можете запустить мгновенную рассылку, запланировать отложенную задачу "
            "или выгрузить логи предыдущих отправлений."
        )
        kb = mailing_menu_kb(is_running=False, is_paused=False)

    await callback.message.edit_text(text, parse_mode="html", reply_markup=kb)
    await callback.answer()


# ==========================================
# Мастер запуска рассылки
# ==========================================

@router.callback_query(F.data == "mail:start_wizard")
async def cb_mail_start_wizard(callback: CallbackQuery, state: FSMContext) -> None:
    """Шаг 1: Выбор шаблона сообщения."""
    if mailing_srv.is_running:
        await callback.answer("Рассылка уже запущена!", show_alert=True)
        return

    templates = await db.get_templates()
    if not templates:
        await callback.answer("Сначала создайте хотя бы один шаблон в разделе «Шаблоны»!", show_alert=True)
        return

    await state.update_data(is_scheduled=False)
    await state.set_state(MailingStates.select_template)

    text = "📝 <b>Шаг 1 из 3: Выберите шаблон для рассылки:</b>"
    await callback.message.edit_text(text, parse_mode="html", reply_markup=select_template_for_mail_kb(templates))
    await callback.answer()


@router.callback_query(F.data == "mail:schedule_wizard")
async def cb_mail_schedule_wizard(callback: CallbackQuery, state: FSMContext) -> None:
    """Старт мастера планирования отложенной рассылки."""
    if mailing_srv.is_running:
        await callback.answer("Рассылка уже активна!", show_alert=True)
        return

    templates = await db.get_templates()
    if not templates:
        await callback.answer("Сначала создайте шаблон в разделе «Шаблоны»!", show_alert=True)
        return

    await state.update_data(is_scheduled=True)
    await state.set_state(MailingStates.select_template)

    text = "⏰ <b>Шаг 1 из 3: Выберите шаблон для отложенной рассылки:</b>"
    await callback.message.edit_text(text, parse_mode="html", reply_markup=select_template_for_mail_kb(templates))
    await callback.answer()


@router.callback_query(F.data.startswith("mail:set_tmpl:"))
async def cb_mail_set_template(callback: CallbackQuery, state: FSMContext) -> None:
    """Шаг 2: Выбор целевой аудитории (категории)."""
    template_id = int(callback.data.split(":")[2])
    await state.update_data(template_id=template_id)
    await state.set_state(MailingStates.select_category)

    categories = await db.get_categories()
    text = (
        "🎯 <b>Шаг 2 из 3: Выберите категорию групп для рассылки:</b>\n"
        "<i>(Или выберите «Все группы», чтобы отправить по всей базе)</i>"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=select_category_for_mail_kb(categories))
    await callback.answer()


@router.callback_query(F.data.startswith("mail:set_cat:"))
async def cb_mail_set_category(callback: CallbackQuery, state: FSMContext) -> None:
    """Шаг 3: Подтверждение мгновенного старта или ввод времени для отложенного."""
    cat_id = int(callback.data.split(":")[2])
    cat_id = None if cat_id == 0 else cat_id
    await state.update_data(category_id=cat_id)

    data = await state.get_data()
    is_scheduled = data.get("is_scheduled", False)
    template_id = data.get("template_id")

    template = await db.get_template_by_id(template_id)
    groups = await db.get_groups(category_id=cat_id, status="active")
    accounts = await db.get_accounts()
    active_accs = [a for a in accounts if a.status == "active"]

    if not groups:
        await callback.answer("В выбранной категории нет активных групп!", show_alert=True)
        return
    if not active_accs:
        await callback.answer("Нет активных аккаунтов для отправки!", show_alert=True)
        return

    if is_scheduled:
        # Переход к вводу времени планировщика
        await state.set_state(MailingStates.enter_schedule_datetime)
        text = (
            "⏰ <b>Шаг 3 из 3: Задайте время запуска</b>\n\n"
            "Отправьте дату и время запуска в формате:\n"
            "<code>ГГГГ-ММ-ДД ЧЧ:ММ</code> (например: <code>2026-08-18 18:30</code>)\n"
            "или просто время сегодня: <code>ЧЧ:ММ</code> (например: <code>21:00</code>)"
        )
        await callback.message.edit_text(text, parse_mode="html", reply_markup=custom_back_kb("menu:mailing", "❌ Отмена"))
        await callback.answer()
        return

    # Мгновенный запуск: показываем экран подтверждения
    await state.set_state(MailingStates.confirm_start)
    cat_name = "Все группы"
    if cat_id:
        c = await db.get_category_by_id(cat_id)
        if c:
            cat_name = c.name

    text = (
        "🚀 <b>Подтверждение запуска авторассылки</b>\n\n"
        f"• Шаблон: <b>«{template.name}»</b>\n"
        f"• Целевая аудитория: <b>{cat_name}</b> (Групп: <b>{len(groups)}</b>)\n"
        f"• Доступных аккаунтов: <b>{len(active_accs)}</b>\n\n"
        "⚡️ Рассылка будет выполняться в фоне с учетом рандомизации задержек и спинтакса.\n\n"
        "<b>Запустить рассылку прямо сейчас?</b>"
    )
    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=confirm_action_kb("mail:confirm_launch", "menu:mailing")
    )
    await callback.answer()


@router.message(MailingStates.enter_schedule_datetime)
async def msg_mail_save_schedule(message: Message, state: FSMContext) -> None:
    """Обработка ввода даты и времени для планировщика."""
    raw_time = (message.text or "").strip()
    data = await state.get_data()
    template_id = data.get("template_id")
    category_id = data.get("category_id")

    scheduled_dt: Optional[datetime] = None

    # Пробуем распарсить полный формат YYYY-MM-DD HH:MM
    try:
        scheduled_dt = datetime.strptime(raw_time, "%Y-%m-%d %H:%M")
    except ValueError:
        # Пробуем распарсить только HH:MM на текущий день
        try:
            t = datetime.strptime(raw_time, "%H:%M").time()
            now = datetime.now()
            scheduled_dt = datetime.combine(now.date(), t)
            if scheduled_dt <= now:
                # Если время сегодня уже прошло, переносим на завтра
                scheduled_dt += timedelta(days=1)
        except ValueError:
            pass

    if not scheduled_dt or scheduled_dt <= datetime.now():
        await message.answer(
            "❌ <b>Некорректная дата или время!</b>\n"
            "Время должно быть в будущем. Пример: <code>2026-08-18 20:00</code> или <code>22:30</code>",
            parse_mode="html",
            reply_markup=custom_back_kb("menu:mailing", "❌ Отмена")
        )
        return

    # Добавляем задачу в планировщик
    job_id = mailing_srv.schedule_mailing(
        run_date=scheduled_dt,
        template_id=template_id,
        category_id=category_id
    )

    await state.clear()
    await message.answer(
        f"✅ <b>Рассылка успешно запланирована!</b>\n\n"
        f"📅 Время запуска: <b>{scheduled_dt.strftime('%d.%m.%Y %H:%M')}</b>\n"
        f"🆔 ID задачи: <code>{job_id}</code>",
        parse_mode="html",
        reply_markup=custom_back_kb("menu:mailing", "🚀 В меню рассылки")
    )


@router.callback_query(F.data == "mail:confirm_launch")
async def cb_mail_confirm_launch(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Старт процесса рассылки в фоновом режиме."""
    data = await state.get_data()
    template_id = data.get("template_id")
    category_id = data.get("category_id")
    await state.clear()

    active_monitor_msg["chat_id"] = callback.message.chat.id
    active_monitor_msg["message_id"] = callback.message.message_id

    # Запускаем рассылку в отдельном asyncio Task
    async def ui_callback():
        await update_monitor_ui(bot)

    asyncio.create_task(
        mailing_srv.run_mailing(
            template_id=template_id,
            category_id=category_id,
            ui_callback=ui_callback
        )
    )

    await callback.answer("Рассылка запущена!")
    await asyncio.sleep(0.5)
    await update_monitor_ui(bot)


# ==========================================
# Управление активной рассылкой (Пауза, Стоп)
# ==========================================

@router.callback_query(F.data == "mail:pause")
async def cb_mail_pause(callback: CallbackQuery, bot: Bot) -> None:
    """Установка рассылки на паузу."""
    mailing_srv.pause()
    await callback.answer("Рассылка приостановлена")
    await update_monitor_ui(bot)


@router.callback_query(F.data == "mail:resume")
async def cb_mail_resume(callback: CallbackQuery, bot: Bot) -> None:
    """Возобновление рассылки."""
    mailing_srv.resume()
    await callback.answer("Рассылка возобновлена")
    await update_monitor_ui(bot)


@router.callback_query(F.data == "mail:stop")
async def cb_mail_stop(callback: CallbackQuery, bot: Bot) -> None:
    """Остановка рассылки."""
    mailing_srv.stop()
    await callback.answer("Остановка рассылки...")
    await asyncio.sleep(0.5)
    await update_monitor_ui(bot)


@router.callback_query(F.data == "mail:refresh")
async def cb_mail_refresh(callback: CallbackQuery, bot: Bot) -> None:
    """Принудительное обновление интерфейса монитора."""
    await update_monitor_ui(bot)
    await callback.answer("Обновлено")
