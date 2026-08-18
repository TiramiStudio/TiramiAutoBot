"""
Роутер для управления глобальными настройками рассылки:
рандомизированные задержки (cooldown), паузы ротации аккаунтов и суточные лимиты.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.database.db import db
from bot.keyboards.inline import settings_menu_kb, custom_back_kb
from bot.utils.helpers import IsAdminFilter
from bot.utils.states import SettingStates

router = Router(name="settings_router")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


@router.callback_query(F.data == "menu:settings")
async def cb_settings_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Главный экран раздела Настройки."""
    await state.clear()
    settings = await db.get_all_settings()

    text = (
        "⚙️ <b>Глобальные настройки безопасности и таймингов</b>\n\n"
        "• <b>Мин./Макс. задержка:</b> случайный интервал между отправками в группы для имитации человека.\n"
        "• <b>Пауза аккаунтов:</b> дополнительное время при переключении между рабочими сессиями.\n"
        "• <b>Лимит на аккаунт:</b> максимальное число сообщений с одного аккаунта за 24 часа.\n\n"
        "Нажмите на параметр для изменения:"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=settings_menu_kb(settings))
    await callback.answer()


@router.callback_query(F.data == "set:min_delay")
async def cb_set_min_delay(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос новой минимальной задержки."""
    await state.set_state(SettingStates.enter_min_delay)
    text = (
        "⏱ <b>Введите минимальную задержку между отправками (в секундах):</b>\n"
        "<i>(Рекомендуется не менее 20–30 секунд)</i>"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=custom_back_kb("menu:settings", "❌ Отмена"))
    await callback.answer()


@router.message(SettingStates.enter_min_delay)
async def msg_save_min_delay(message: Message, state: FSMContext) -> None:
    """Сохранение минимальной задержки."""
    val = (message.text or "").strip()
    if not val.isdigit() or int(val) < 1:
        await message.answer("❌ Введите положительное целое число секунд:")
        return

    await db.set_setting("min_delay", val)
    await state.clear()
    await message.answer(f"✅ Минимальная задержка установлена на <b>{val}с</b>.", parse_mode="html", reply_markup=custom_back_kb("menu:settings", "⚙️ В настройки"))


@router.callback_query(F.data == "set:max_delay")
async def cb_set_max_delay(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос новой максимальной задержки."""
    await state.set_state(SettingStates.enter_max_delay)
    text = (
        "⏱ <b>Введите максимальную задержку между отправками (в секундах):</b>\n"
        "<i>(Рекомендуется от 60 до 180 секунд)</i>"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=custom_back_kb("menu:settings", "❌ Отмена"))
    await callback.answer()


@router.message(SettingStates.enter_max_delay)
async def msg_save_max_delay(message: Message, state: FSMContext) -> None:
    """Сохранение максимальной задержки."""
    val = (message.text or "").strip()
    if not val.isdigit() or int(val) < 1:
        await message.answer("❌ Введите положительное целое число секунд:")
        return

    await db.set_setting("max_delay", val)
    await state.clear()
    await message.answer(f"✅ Максимальная задержка установлена на <b>{val}с</b>.", parse_mode="html", reply_markup=custom_back_kb("menu:settings", "⚙️ В настройки"))


@router.callback_query(F.data == "set:account_delay")
async def cb_set_account_delay(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос паузы между сменой аккаунтов."""
    await state.set_state(SettingStates.enter_account_delay)
    text = "🔄 <b>Введите задержку при переключении между разными аккаунтами (в секундах):</b>"
    await callback.message.edit_text(text, parse_mode="html", reply_markup=custom_back_kb("menu:settings", "❌ Отмена"))
    await callback.answer()


@router.message(SettingStates.enter_account_delay)
async def msg_save_account_delay(message: Message, state: FSMContext) -> None:
    """Сохранение паузы между аккаунтами."""
    val = (message.text or "").strip()
    if not val.isdigit() or int(val) < 0:
        await message.answer("❌ Введите целое неотрицательное число секунд:")
        return

    await db.set_setting("account_delay", val)
    await state.clear()
    await message.answer(f"✅ Пауза ротации аккаунтов установлена на <b>{val}с</b>.", parse_mode="html", reply_markup=custom_back_kb("menu:settings", "⚙️ В настройки"))


@router.callback_query(F.data == "set:daily_limit")
async def cb_set_daily_limit(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос суточного лимита отправок на один аккаунт."""
    await state.set_state(SettingStates.enter_daily_limit)
    text = (
        "📊 <b>Введите дневной лимит сообщений на один аккаунт:</b>\n"
        "<i>(При достижении лимита аккаунт будет отдыхать до конца суток)</i>"
    )
    await callback.message.edit_text(text, parse_mode="html", reply_markup=custom_back_kb("menu:settings", "❌ Отмена"))
    await callback.answer()


@router.message(SettingStates.enter_daily_limit)
async def msg_save_daily_limit(message: Message, state: FSMContext) -> None:
    """Сохранение дневного лимита на аккаунт."""
    val = (message.text or "").strip()
    if not val.isdigit() or int(val) < 1:
        await message.answer("❌ Введите положительное число сообщений:")
        return

    await db.set_setting("daily_limit_per_account", val)
    await state.clear()
    await message.answer(f"✅ Суточный лимит на аккаунт установлен: <b>{val} сообщений</b>.", parse_mode="html", reply_markup=custom_back_kb("menu:settings", "⚙️ В настройки"))
