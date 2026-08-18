"""
Роутер для управления целевыми группами: ручное добавление списком,
автопарсинг диалогов аккаунтов, категории и пагинация.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from bot.database.db import db
from bot.database.models import Group, Category, Account
from bot.keyboards.inline import (
    groups_menu_kb,
    groups_pagination_kb,
    group_detail_kb,
    categories_menu_kb,
    select_category_for_groups_kb,
    custom_back_kb,
    confirm_action_kb
)
from bot.services.telethon_manager import telethon_mgr
from bot.utils.helpers import IsAdminFilter, normalize_telegram_target
from bot.utils.states import GroupStates

router = Router(name="groups_router")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())

ITEMS_PER_PAGE = 8


@router.callback_query(F.data == "menu:groups")
async def cb_groups_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Главное меню раздела Группы."""
    await state.clear()
    total_count = await db.count_groups()
    text = (
        "👥 <b>Управление целевыми группами и каналами</b>\n\n"
        f"Всего групп в базе: <b>{total_count}</b>\n\n"
        "Выберите действие в меню ниже:"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=groups_menu_kb(total_count))
    await callback.answer()


# ==========================================
# Ручное добавление групп
# ==========================================

@router.callback_query(F.data == "grp:add_manual")
async def cb_groups_add_manual_select_cat(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор категории перед ручным добавлением групп."""
    categories = await db.get_categories()
    text = (
        "📁 <b>Выберите категорию для добавляемых групп</b>\n"
        "<i>(Или выберите «Без категории», чтобы добавить в общий список)</i>"
    )
    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=select_category_for_groups_kb(categories)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("addgrp:cat:"))
async def cb_groups_add_manual_enter(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос списка ссылок/юзернеймов на группы."""
    cat_id = int(callback.data.split(":")[2])
    cat_id = None if cat_id == 0 else cat_id
    await state.update_data(category_id=cat_id)
    await state.set_state(GroupStates.enter_targets)

    text = (
        "✍️ <b>Отправьте список групп для добавления</b>\n\n"
        "Вы можете отправить одну или несколько ссылок/юзернеймов (каждую с новой строки).\n\n"
        "<b>Поддерживаемые форматы:</b>\n"
        "• <code>@group_username</code>\n"
        "• <code>https://t.me/group_username</code>\n"
        "• <code>https://t.me/+joinchat_hash</code>\n"
        "• <code>-1001234567890</code>"
    )
    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=custom_back_kb("menu:groups", "❌ Отмена")
    )
    await callback.answer()


@router.message(GroupStates.enter_targets)
async def msg_groups_save_targets(message: Message, state: FSMContext) -> None:
    """Обработка и сохранение введенных пользователем групп."""
    raw_text = message.text or ""
    lines = raw_text.splitlines()

    data = await state.get_data()
    category_id = data.get("category_id")

    items_to_add = []
    for line in lines:
        target = normalize_telegram_target(line)
        if target:
            items_to_add.append({"target": target, "title": target})

    if not items_to_add:
        await message.answer(
            "❌ Не найдено корректных ссылок или юзернеймов. Попробуйте еще раз:",
            reply_markup=custom_back_kb("menu:groups", "❌ Отмена")
        )
        return

    added_count = await db.add_groups_bulk(items_to_add, category_id=category_id)
    await state.clear()

    await message.answer(
        f"✅ <b>Успешно обработано: {added_count} групп!</b>\n"
        "Они добавлены в базу данных и готовы для рассылки.",
        parse_mode="html",
        reply_markup=custom_back_kb("menu:groups", "👥 В меню групп")
    )


# ==========================================
# Автопарсинг групп с аккаунта
# ==========================================

@router.callback_query(F.data == "grp:parse_select_acc")
async def cb_groups_parse_select_acc(callback: CallbackQuery) -> None:
    """Выбор аккаунта для парсинга диалогов."""
    accounts = await db.get_accounts()
    active_accounts = [a for a in accounts if a.status == "active"]

    if not active_accounts:
        await callback.answer("Нет активных аккаунтов для парсинга!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for acc in active_accounts:
        builder.row(
            InlineKeyboardButton(
                text=f"📱 {acc.first_name or acc.phone} ({acc.phone})",
                callback_data=f"acc:parse:{acc.id}"
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:groups"))

    text = "📥 <b>Выберите аккаунт, из которого нужно выгрузить группы:</b>"
    await callback.message.edit_text(text, parse_mode="html", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("acc:parse:"))
async def cb_account_parse_exec(callback: CallbackQuery) -> None:
    """Запуск процесса парсинга диалогов аккаунта."""
    account_id = int(callback.data.split(":")[2])
    account = await db.get_account_by_id(account_id)

    if not account:
        await callback.answer("Аккаунт не найден!", show_alert=True)
        return

    await callback.message.edit_text(
        f"⏳ <i>Парсим группы и супергруппы с аккаунта {account.phone}... Пожалуйста, подождите.</i>",
        parse_mode="html"
    )

    try:
        parsed_groups = await telethon_mgr.parse_account_dialogs(account)
        if not parsed_groups:
            await callback.message.edit_text(
                f"ℹ️ У аккаунта <code>{account.phone}</code> не найдено доступных групп.",
                parse_mode="html",
                reply_markup=custom_back_kb("menu:groups", "👥 В меню групп")
            )
            return

        added_count = await db.add_groups_bulk(parsed_groups)
        await callback.message.edit_text(
            f"✅ <b>Парсинг успешно завершен!</b>\n\n"
            f"Найдено групп: <b>{len(parsed_groups)}</b>\n"
            f"Добавлено/обновлено в базе: <b>{added_count}</b>",
            parse_mode="html",
            reply_markup=custom_back_kb("menu:groups", "👥 В меню групп")
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка при парсинге групп:</b>\n{e}",
            parse_mode="html",
            reply_markup=custom_back_kb("menu:groups", "👥 В меню групп")
        )


# ==========================================
# Просмотр и пагинация списка групп
# ==========================================

@router.callback_query(F.data.startswith("grp:list:"))
async def cb_groups_list(callback: CallbackQuery) -> None:
    """Пагинированный просмотр целевых групп."""
    page = int(callback.data.split(":")[2])
    groups = await db.get_groups()

    if not groups:
        await callback.answer("Список групп пуст!", show_alert=True)
        return

    total_pages = (len(groups) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))

    page_groups = groups[page * ITEMS_PER_PAGE: (page + 1) * ITEMS_PER_PAGE]

    text = (
        f"📋 <b>Список целевых групп</b> (Всего: <b>{len(groups)}</b>):\n\n"
        "🟢 — Активна\n"
        "🔴 — Ограничена / Недоступна\n\n"
        "Нажмите на группу для подробностей:"
    )
    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=groups_pagination_kb(page_groups, page, total_pages)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("grp:view:"))
async def cb_group_view(callback: CallbackQuery) -> None:
    """Карточка конкретной группы."""
    group_id = int(callback.data.split(":")[2])
    group = await db.get_group_by_id(group_id)

    if not group:
        await callback.answer("Группа не найдена!", show_alert=True)
        return

    cat_name = "Без категории"
    if group.category_id:
        cat = await db.get_category_by_id(group.category_id)
        if cat:
            cat_name = cat.name

    status_str = "🟢 Активна" if group.status == "active" else f"🔴 {group.status}"

    text = (
        f"👥 <b>Информация о группе:</b>\n\n"
        f"• Название: <b>{group.title}</b>\n"
        f"• Цель: <code>{group.target}</code>\n"
        f"• Категория: <b>{cat_name}</b>\n"
        f"• Статус: <b>{status_str}</b>\n"
        f"• Добавлена: <code>{group.created_at[:19]}</code>"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=group_detail_kb(group.id))
    await callback.answer()


@router.callback_query(F.data.startswith("grp:delete:"))
async def cb_group_delete(callback: CallbackQuery) -> None:
    """Удаление группы."""
    group_id = int(callback.data.split(":")[2])
    await db.delete_group(group_id)
    await callback.answer("Группа удалена!", show_alert=True)
    await cb_groups_list(callback)


@router.callback_query(F.data == "grp:clear_ask")
async def cb_groups_clear_ask(callback: CallbackQuery) -> None:
    """Запрос подтверждения очистки всех групп."""
    text = "⚠️ <b>Вы действительно хотите удалить ВСЕ группы из базы данных?</b>"
    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=confirm_action_kb("grp:clear_confirm", "menu:groups")
    )
    await callback.answer()


@router.callback_query(F.data == "grp:clear_confirm")
async def cb_groups_clear_confirm(callback: CallbackQuery) -> None:
    """Полная очистка групп."""
    await db.clear_all_groups()
    await callback.answer("Все группы успешно удалены!", show_alert=True)
    await cb_groups_menu(callback, None)


# ==========================================
# Управление категориями
# ==========================================

@router.callback_query(F.data == "grp:categories")
async def cb_categories_menu(callback: CallbackQuery) -> None:
    """Меню категорий."""
    categories = await db.get_categories()
    text = (
        "📁 <b>Категории и теги целевых групп</b>\n\n"
        "Категории позволяют группировать чаты по тематикам или языкам "
        "и запускать рассылку точечно."
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=categories_menu_kb(categories))
    await callback.answer()


@router.callback_query(F.data == "cat:add")
async def cb_category_add(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос названия новой категории."""
    await state.set_state(GroupStates.enter_category_name)
    text = "📁 <b>Введите название новой категории:</b>"
    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=custom_back_kb("grp:categories", "❌ Отмена")
    )
    await callback.answer()


@router.message(GroupStates.enter_category_name)
async def msg_category_save(message: Message, state: FSMContext) -> None:
    """Сохранение новой категории."""
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ Название не может быть пустым.")
        return

    await db.add_category(name)
    await state.clear()
    await message.answer(
        f"✅ Категория <b>{name}</b> успешно создана!",
        parse_mode="html",
        reply_markup=custom_back_kb("grp:categories", "📁 К категориям")
    )


@router.callback_query(F.data.startswith("cat:delete:"))
async def cb_category_delete(callback: CallbackQuery) -> None:
    """Удаление категории."""
    cat_id = int(callback.data.split(":")[2])
    await db.delete_category(cat_id)
    await callback.answer("Категория удалена!", show_alert=True)
    await cb_categories_menu(callback)
