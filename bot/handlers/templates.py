"""
Роутер для управления шаблонами сообщений: создание, поддержка текста,
фото, видео, документов, медиагрупп, спинтакса, предпросмотра и форматирования.
"""

import json
import os
import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import MEDIA_DIR
from bot.database.db import db
from bot.database.models import Template
from bot.keyboards.inline import (
    templates_menu_kb,
    template_detail_kb,
    custom_back_kb,
    confirm_action_kb
)
from bot.services.spintax import generate_spintax_samples, has_spintax
from bot.utils.helpers import IsAdminFilter
from bot.utils.states import TemplateStates

router = Router(name="templates_router")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


@router.callback_query(F.data == "menu:templates")
async def cb_templates_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Главное меню раздела Шаблоны."""
    await state.clear()
    templates = await db.get_templates()
    text = (
        "📝 <b>Управление шаблонами сообщений</b>\n\n"
        f"Всего сохранено шаблонов: <b>{len(templates)}</b>\n\n"
        "Шаблоны поддерживают форматирование HTML (жирный, курсив, ссылки), "
        "медиафайлы (фото, видео, документы) и <b>спинтакс</b> для рандомизации текста."
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=templates_menu_kb(templates))
    await callback.answer()


@router.callback_query(F.data == "tmpl:add")
async def cb_template_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало создания шаблона: запрос названия."""
    await state.set_state(TemplateStates.enter_name)
    text = (
        "📝 <b>Создание нового шаблона</b>\n\n"
        "Введите короткое и понятное <b>название</b> для шаблона (например: <i>Акция Лето</i>):"
    )
    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=custom_back_kb("menu:templates", "❌ Отмена")
    )
    await callback.answer()


@router.message(TemplateStates.enter_name)
async def msg_template_enter_name(message: Message, state: FSMContext) -> None:
    """Обработка ввода названия шаблона."""
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ Название не может быть пустым. Введите название:")
        return

    await state.update_data(name=name)
    await state.set_state(TemplateStates.enter_content)

    text = (
        f"📝 <b>Шаблон: «{name}»</b>\n\n"
        "Теперь отправьте <b>сообщение</b>, которое будет рассылаться:\n\n"
        "• Это может быть просто текст, либо <b>фото / видео / документ</b> с подписью.\n"
        "• Поддерживается форматирование: <b>жирный</b>, <i>курсив</i>, <code>код</code>, ссылки.\n"
        "• Поддерживается <b>спинтакс</b>: <code>{Привет|Здравствуйте|Добрый день}</code>, "
        "<code>{уважаемый|дорогой} {друг|партнер}</code>."
    )
    await message.answer(text, parse_mode="html", reply_markup=custom_back_kb("menu:templates", "❌ Отмена"))


@router.message(TemplateStates.enter_content)
async def msg_template_save_content(message: Message, state: FSMContext, bot: Bot) -> None:
    """Сохранение контента шаблона (текст / медиафайлы)."""
    data = await state.get_data()
    name = data.get("name", "Без названия")

    media_type = "text"
    media_files = []
    text_content = ""

    # Проверяем тип входящего сообщения
    if message.photo:
        media_type = "photo"
        text_content = message.html_text or message.caption or ""
        photo = message.photo[-1]
        file_ext = ".jpg"
        file_path = MEDIA_DIR / f"photo_{uuid.uuid4().hex[:10]}{file_ext}"
        await bot.download(photo, destination=file_path)
        media_files.append(str(file_path))

    elif message.video:
        media_type = "video"
        text_content = message.html_text or message.caption or ""
        file_ext = ".mp4"
        file_path = MEDIA_DIR / f"video_{uuid.uuid4().hex[:10]}{file_ext}"
        await bot.download(message.video, destination=file_path)
        media_files.append(str(file_path))

    elif message.document:
        media_type = "document"
        text_content = message.html_text or message.caption or ""
        orig_name = message.document.file_name or "file"
        file_ext = os.path.splitext(orig_name)[1] or ".dat"
        file_path = MEDIA_DIR / f"doc_{uuid.uuid4().hex[:10]}{file_ext}"
        await bot.download(message.document, destination=file_path)
        media_files.append(str(file_path))

    else:
        # Обычный текст
        text_content = message.html_text or message.text or ""

    if not text_content and not media_files:
        await message.answer("❌ Сообщение не содержит текста или медиа. Отправьте заново:")
        return

    # Сохраняем шаблон в БД
    template_id = await db.add_template(
        name=name,
        text=text_content,
        media_type=media_type,
        media_files=media_files
    )

    await state.clear()

    spintax_info = "⚡️ <b>Обнаружен спинтакс:</b> текст будет уникализироваться для каждой отправки!" if has_spintax(text_content) else "ℹ️ Спинтакс не используется."

    await message.answer(
        f"✅ <b>Шаблон «{name}» успешно сохранен!</b>\n\n"
        f"• Тип: <b>{media_type}</b>\n"
        f"• {spintax_info}",
        parse_mode="html",
        reply_markup=template_detail_kb(template_id)
    )


@router.callback_query(F.data.startswith("tmpl:view:"))
async def cb_template_view(callback: CallbackQuery) -> None:
    """Просмотр карточки шаблона."""
    template_id = int(callback.data.split(":")[2])
    template = await db.get_template_by_id(template_id)

    if not template:
        await callback.answer("Шаблон не найден!", show_alert=True)
        return

    media_files = json.loads(template.media_files) if template.media_files else []
    media_info = f"файлов: {len(media_files)}" if media_files else "без медиа"

    text = (
        f"📝 <b>Шаблон: «{template.name}»</b>\n\n"
        f"• Тип контента: <b>{template.media_type}</b> ({media_info})\n"
        f"• Создан: <code>{template.created_at[:19]}</code>\n\n"
        f"<b>Текст шаблона:</b>\n"
        f"<blockquote>{template.text or '<i>(только медиа)</i>'}</blockquote>"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=template_detail_kb(template.id))
    await callback.answer()


@router.callback_query(F.data.startswith("tmpl:preview:"))
async def cb_template_preview(callback: CallbackQuery) -> None:
    """Генерация и отображение примеров рандомизации текста (спинтакс-предпросмотр)."""
    template_id = int(callback.data.split(":")[2])
    template = await db.get_template_by_id(template_id)

    if not template:
        await callback.answer("Шаблон не найден!", show_alert=True)
        return

    samples = generate_spintax_samples(template.text, count=3)

    text = f"👁 <b>Предпросмотр спинтакса для «{template.name}»:</b>\n\n"
    for i, s in enumerate(samples, 1):
        text += f"<b>Вариант #{i}:</b>\n<blockquote>{s}</blockquote>\n\n"

    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=custom_back_kb(f"tmpl:view:{template.id}", "🔙 К карточке шаблона")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tmpl:delete_ask:"))
async def cb_template_delete_ask(callback: CallbackQuery) -> None:
    """Запрос подтверждения удаления шаблона."""
    template_id = int(callback.data.split(":")[2])
    text = "⚠️ <b>Вы уверены, что хотите удалить этот шаблон?</b>"
    await callback.message.edit_text(
        text,
        parse_mode="html",
        reply_markup=confirm_action_kb(f"tmpl:delete_confirm:{template_id}", f"tmpl:view:{template_id}")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tmpl:delete_confirm:"))
async def cb_template_delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтвержденное удаление шаблона."""
    template_id = int(callback.data.split(":")[2])
    template = await db.get_template_by_id(template_id)

    if template and template.media_files:
        files = json.loads(template.media_files)
        for f in files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    await db.delete_template(template_id)
    await callback.answer("Шаблон удален!", show_alert=True)
    await cb_templates_menu(callback, state)
