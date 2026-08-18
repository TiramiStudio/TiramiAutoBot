"""
Роутер для управления аккаунтами: добавление сессий Telethon, авторизация,
проверка статусов, 2FA и удаление.
"""

import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.database.db import db
from bot.database.models import Account
from bot.keyboards.inline import (
    accounts_list_kb,
    account_detail_kb,
    back_to_main_kb,
    custom_back_kb,
    confirm_action_kb
)
from bot.services.telethon_manager import telethon_mgr
from bot.utils.helpers import IsAdminFilter, clean_phone_number
from bot.utils.states import AccountStates

router = Router(name="accounts_router")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


@router.callback_query(F.data == "menu:accounts")
async def cb_accounts_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Список всех подключенных аккаунтов."""
    await state.clear()
    accounts = await db.get_accounts()
    
    text = (
        "📱 <b>Управление Telegram-аккаунтами</b>\n\n"
        f"Всего подключено аккаунтов: <b>{len(accounts)}</b>\n\n"
        "🟢 — Активен и готов к работе\n"
        "🟡 — Временный флуд-бан (FloodWait)\n"
        "🔴 — Не авторизован или заблокирован\n\n"
        "Нажмите на нужный аккаунт для подробностей или добавьте новый:"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=accounts_list_kb(accounts))
    await callback.answer()


@router.callback_query(F.data == "acc:add")
async def cb_account_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало процесса привязки нового аккаунта."""
    await state.set_state(AccountStates.enter_phone)
    text = (
        "📱 <b>Добавление нового аккаунта</b>\n\n"
        "Отправьте номер телефона в международном формате (например, <code>+79991234567</code>):\n\n"
        "<i>На этот номер будет отправлен код подтверждения в официальном приложении Telegram.</i>"
    )
    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=custom_back_kb("menu:accounts", "❌ Отмена")
    )
    await callback.answer()


@router.message(AccountStates.enter_phone)
async def msg_account_enter_phone(message: Message, state: FSMContext) -> None:
    """Обработка ввода номера телефона и запрос кода подтверждения."""
    raw_phone = message.text or ""
    phone = clean_phone_number(raw_phone)

    if not phone or len(phone) < 10:
        await message.answer(
            "❌ <b>Некорректный формат номера!</b>\nПожалуйста, отправьте номер в виде <code>+79991234567</code>:",
            parse_mode="html",
            reply_markup=custom_back_kb("menu:accounts", "❌ Отмена")
        )
        return

    wait_msg = await message.answer("⏳ <i>Отправляем запрос на получение кода авторизации...</i>", parse_mode="html")

    result = await telethon_mgr.request_code(phone=phone)

    if not result.get("success"):
        await wait_msg.edit_text(
            f"❌ <b>Ошибка при запросе кода:</b>\n{result.get('error', 'Неизвестная ошибка')}",
            parse_mode="html",
            reply_markup=custom_back_kb("menu:accounts", "🔙 Назад")
        )
        await state.clear()
        return

    await state.update_data(phone=phone, phone_code_hash=result["phone_code_hash"])
    await state.set_state(AccountStates.enter_code)

    await wait_msg.edit_text(
        f"📩 <b>Код подтверждения отправлен на номер <code>{phone}</code>!</b>\n\n"
        "Пожалуйста, проверьте служебное сообщение в Telegram и отправьте код сюда.\n"
        "<i>(Если код содержит пробелы или дефисы, можете отправлять как есть)</i>",
        parse_mode="html",
        reply_markup=custom_back_kb("menu:accounts", "❌ Отмена")
    )


@router.message(AccountStates.enter_code)
async def msg_account_enter_code(message: Message, state: FSMContext) -> None:
    """Обработка ввода кода подтверждения."""
    code_raw = message.text or ""
    # Очищаем код от пробелов
    code = code_raw.strip().replace(" ", "").replace("-", "")

    data = await state.get_data()
    phone = data.get("phone", "")

    if not code:
        await message.answer("❌ Код не может быть пустым. Введите код:")
        return

    wait_msg = await message.answer("⏳ <i>Проверяем код подтверждения...</i>", parse_mode="html")
    result = await telethon_mgr.submit_code(phone=phone, code=code)

    if not result.get("success"):
        await wait_msg.edit_text(
            f"❌ <b>Ошибка:</b> {result.get('error')}\n\nПопробуйте ввести код еще раз:",
            parse_mode="html",
            reply_markup=custom_back_kb("menu:accounts", "❌ Отмена")
        )
        return

    # Если требуется двухфакторный пароль (2FA)
    if result.get("needs_2fa"):
        await state.set_state(AccountStates.enter_password)
        await wait_msg.edit_text(
            "🔐 <b>На аккаунте установлена двухфакторная аутентификация (2FA)!</b>\n\n"
            "Пожалуйста, отправьте пароль от вашего аккаунта:",
            parse_mode="html",
            reply_markup=custom_back_kb("menu:accounts", "❌ Отмена")
        )
        return

    # Успешный вход без 2FA
    user = result.get("user")
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Без имени"
    username = f"@{user.username}" if user.username else "нет username"

    await state.clear()
    await wait_msg.edit_text(
        f"✅ <b>Аккаунт успешно подключен!</b>\n\n"
        f"👤 Имя: <b>{name}</b>\n"
        f"🔗 Юзернейм: <b>{username}</b>\n"
        f"📱 Номер: <code>{phone}</code>",
        parse_mode="html",
        reply_markup=custom_back_kb("menu:accounts", "📱 К списку аккаунтов")
    )


@router.message(AccountStates.enter_password)
async def msg_account_enter_password(message: Message, state: FSMContext) -> None:
    """Обработка ввода пароля 2FA."""
    password = message.text or ""
    data = await state.get_data()
    phone = data.get("phone", "")

    wait_msg = await message.answer("⏳ <i>Проверяем пароль 2FA...</i>", parse_mode="html")
    result = await telethon_mgr.submit_password(phone=phone, password=password)

    if not result.get("success"):
        await wait_msg.edit_text(
            f"❌ <b>Ошибка:</b> {result.get('error')}\n\nПопробуйте ввести пароль еще раз:",
            parse_mode="html",
            reply_markup=custom_back_kb("menu:accounts", "❌ Отмена")
        )
        return

    user = result.get("user")
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Без имени"
    username = f"@{user.username}" if user.username else "нет username"

    await state.clear()
    await wait_msg.edit_text(
        f"✅ <b>Аккаунт с 2FA успешно подключен!</b>\n\n"
        f"👤 Имя: <b>{name}</b>\n"
        f"🔗 Юзернейм: <b>{username}</b>\n"
        f"📱 Номер: <code>{phone}</code>",
        parse_mode="html",
        reply_markup=custom_back_kb("menu:accounts", "📱 К списку аккаунтов")
    )


@router.callback_query(F.data.startswith("acc:view:"))
async def cb_account_view(callback: CallbackQuery) -> None:
    """Просмотр детальной карточки аккаунта."""
    account_id = int(callback.data.split(":")[2])
    account: Account = await db.get_account_by_id(account_id)

    if not account:
        await callback.answer("Аккаунт не найден!", show_alert=True)
        return

    status_map = {
        "active": "🟢 Активен",
        "flood_wait": "🟡 Флуд-бан",
        "unauthorized": "🔴 Не авторизован",
        "banned": "🔴 Заблокирован Telegram"
    }
    status_str = status_map.get(account.status, f"⚪️ {account.status}")

    today_sent = await db.get_today_sent_count_for_account(account.phone)

    text = (
        f"📱 <b>Информация об аккаунте:</b>\n\n"
        f"• Номер: <code>{account.phone}</code>\n"
        f"• Имя: <b>{account.first_name or '—'}</b>\n"
        f"• Юзернейм: <b>{('@' + account.username) if account.username else '—'}</b>\n"
        f"• Статус: <b>{status_str}</b>\n"
        f"• Отправок сегодня: <b>{today_sent}</b>\n"
        f"• Подключен: <code>{account.created_at[:19]}</code>\n"
        f"• Посл. активность: <code>{account.last_used_at[:19] if account.last_used_at else '—'}</code>"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=account_detail_kb(account.id))
    await callback.answer()


@router.callback_query(F.data.startswith("acc:check:"))
async def cb_account_check(callback: CallbackQuery) -> None:
    """Проверка актуального статуса сессии аккаунта."""
    account_id = int(callback.data.split(":")[2])
    account = await db.get_account_by_id(account_id)

    if not account:
        await callback.answer("Аккаунт не найден!", show_alert=True)
        return

    await callback.answer("Проверяем статус сессии...", show_alert=False)
    res = await telethon_mgr.check_account_status(account)

    if res.get("status") == "active":
        msg = f"✅ Аккаунт активен!\nИмя: {res.get('first_name')} (@{res.get('username')})"
    else:
        msg = f"⚠️ Статус: {res.get('status')}\n{res.get('message', '')}"

    await callback.answer(msg, show_alert=True)
    # Обновляем экран аккаунта
    await cb_account_view(callback)


@router.callback_query(F.data == "acc:check_all")
async def cb_account_check_all(callback: CallbackQuery) -> None:
    """Массовая проверка всех подключенных аккаунтов."""
    accounts = await db.get_accounts()
    if not accounts:
        await callback.answer("Список аккаунтов пуст!", show_alert=True)
        return

    await callback.answer("Запущена проверка всех аккаунтов...", show_alert=False)
    for acc in accounts:
        await telethon_mgr.check_account_status(acc)

    await callback.answer("Проверка всех аккаунтов завершена!", show_alert=True)
    await cb_accounts_menu(callback, None)


@router.callback_query(F.data.startswith("acc:delete_ask:"))
async def cb_account_delete_ask(callback: CallbackQuery) -> None:
    """Запрос подтверждения удаления аккаунта."""
    account_id = int(callback.data.split(":")[2])
    text = "⚠️ <b>Вы действительно хотите удалить этот аккаунт и его сессию?</b>"
    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=confirm_action_kb(f"acc:delete_confirm:{account_id}", f"acc:view:{account_id}")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("acc:delete_confirm:"))
async def cb_account_delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтвержденное удаление аккаунта."""
    account_id = int(callback.data.split(":")[2])
    session_name = await db.delete_account(account_id)

    if session_name:
        session_file = telethon_mgr.get_session_path(f"{session_name}.session")
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except Exception:
                pass

    await callback.answer("Аккаунт успешно удален!", show_alert=True)
    await cb_accounts_menu(callback, state)
