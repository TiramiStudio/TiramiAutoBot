"""
Модуль создания инлайн-клавиатур (InlineKeyboardMarkup) для всех разделов бота.
"""

from typing import Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.models import Account, Category, Group, Template


def main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню бота."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📱 Аккаунты", callback_data="menu:accounts"),
        InlineKeyboardButton(text="👥 Группы", callback_data="menu:groups")
    )
    builder.row(
        InlineKeyboardButton(text="📝 Шаблоны", callback_data="menu:templates"),
        InlineKeyboardButton(text="🚀 Рассылка", callback_data="menu:mailing")
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="menu:stats")
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ О студии & Соцсети", callback_data="menu:about")
    )
    return builder.as_markup()


def about_kb() -> InlineKeyboardMarkup:
    """Клавиатура с социальными сетями TiramiStudio."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Telegram-канал", url="https://t.me/tiramistudio"),
        InlineKeyboardButton(text="💬 Discord-сервер", url="https://discord.gg/BcQEwxhT45")
    )
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def back_to_main_kb() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def custom_back_kb(target: str, text: str = "🔙 Назад") -> InlineKeyboardMarkup:
    """Универсальная кнопка возврата по callback_data."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=text, callback_data=target))
    return builder.as_markup()


def confirm_action_kb(confirm_cb: str, cancel_cb: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия (Да / Отмена)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_cb),
        InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_cb)
    )
    return builder.as_markup()


# ==========================================
# Клавиатуры для раздела Аккаунты
# ==========================================

def accounts_list_kb(accounts: list[Account]) -> InlineKeyboardMarkup:
    """Список подключенных аккаунтов и действия."""
    builder = InlineKeyboardBuilder()
    for acc in accounts:
        status_icon = "🟢" if acc.status == "active" else ("🟡" if acc.status == "flood_wait" else "🔴")
        display_name = acc.first_name or acc.username or acc.phone
        builder.row(
            InlineKeyboardButton(
                text=f"{status_icon} {display_name} ({acc.phone})",
                callback_data=f"acc:view:{acc.id}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="acc:add"),
        InlineKeyboardButton(text="🔄 Проверить все", callback_data="acc:check_all")
    )
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def account_detail_kb(account_id: int) -> InlineKeyboardMarkup:
    """Карточка отдельного аккаунта."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Проверить статус", callback_data=f"acc:check:{account_id}"),
        InlineKeyboardButton(text="📥 Спарсить группы", callback_data=f"acc:parse:{account_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data=f"acc:delete_ask:{account_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 К списку аккаунтов", callback_data="menu:accounts"))
    return builder.as_markup()


# ==========================================
# Клавиатуры для раздела Группы
# ==========================================

def groups_menu_kb(total_groups: int) -> InlineKeyboardMarkup:
    """Меню управления целевыми группами."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить вручную", callback_data="grp:add_manual"),
        InlineKeyboardButton(text="📥 Спарсить с аккаунта", callback_data="grp:parse_select_acc")
    )
    builder.row(
        InlineKeyboardButton(text=f"📋 Список групп ({total_groups})", callback_data="grp:list:0"),
        InlineKeyboardButton(text="📁 Категории / Теги", callback_data="grp:categories")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Очистить все группы", callback_data="grp:clear_ask")
    )
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def groups_pagination_kb(groups: list[Group], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Пагинация списка групп."""
    builder = InlineKeyboardBuilder()
    for g in groups:
        status_icon = "🟢" if g.status == "active" else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{status_icon} {g.title[:20]} ({g.target[:15]})",
                callback_data=f"grp:view:{g.id}"
            )
        )

    # Кнопки навигации
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"grp:list:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{max(1, total_pages)}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="След. ➡️", callback_data=f"grp:list:{page + 1}"))
    if nav_row:
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="🔙 В меню групп", callback_data="menu:groups"))
    return builder.as_markup()


def group_detail_kb(group_id: int) -> InlineKeyboardMarkup:
    """Карточка конкретной группы."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить группу", callback_data=f"grp:delete:{group_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 К списку групп", callback_data="grp:list:0"))
    return builder.as_markup()


def categories_menu_kb(categories: list[Category]) -> InlineKeyboardMarkup:
    """Список категорий."""
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.row(
            InlineKeyboardButton(text=f"📁 {cat.name}", callback_data=f"cat:view:{cat.id}"),
            InlineKeyboardButton(text="❌", callback_data=f"cat:delete:{cat.id}")
        )
    builder.row(InlineKeyboardButton(text="➕ Создать категорию", callback_data="cat:add"))
    builder.row(InlineKeyboardButton(text="🔙 В меню групп", callback_data="menu:groups"))
    return builder.as_markup()


def select_category_for_groups_kb(categories: list[Category]) -> InlineKeyboardMarkup:
    """Выбор категории при добавлении групп."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🌐 Без категории (Общая)", callback_data="addgrp:cat:0"))
    for cat in categories:
        builder.row(InlineKeyboardButton(text=f"📁 {cat.name}", callback_data=f"addgrp:cat:{cat.id}"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="menu:groups"))
    return builder.as_markup()


# ==========================================
# Клавиатуры для раздела Шаблоны
# ==========================================

def templates_menu_kb(templates: list[Template]) -> InlineKeyboardMarkup:
    """Список созданных шаблонов."""
    builder = InlineKeyboardBuilder()
    for tmpl in templates:
        media_icon = "📝" if tmpl.media_type == "text" else "🖼"
        builder.row(
            InlineKeyboardButton(
                text=f"{media_icon} {tmpl.name}",
                callback_data=f"tmpl:view:{tmpl.id}"
            )
        )
    builder.row(InlineKeyboardButton(text="➕ Создать шаблон", callback_data="tmpl:add"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def template_detail_kb(template_id: int) -> InlineKeyboardMarkup:
    """Карточка шаблона."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👁 Предпросмотр (спинтакс)", callback_data=f"tmpl:preview:{template_id}"),
        InlineKeyboardButton(text="🗑 Удалить шаблон", callback_data=f"tmpl:delete_ask:{template_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 К шаблонам", callback_data="menu:templates"))
    return builder.as_markup()


# ==========================================
# Клавиатуры для раздела Рассылка
# ==========================================

def mailing_menu_kb(is_running: bool, is_paused: bool) -> InlineKeyboardMarkup:
    """Меню управления процессом рассылки."""
    builder = InlineKeyboardBuilder()
    if is_running:
        if is_paused:
            builder.row(
                InlineKeyboardButton(text="▶️ Возобновить", callback_data="mail:resume"),
                InlineKeyboardButton(text="⏹ Остановить", callback_data="mail:stop")
            )
        else:
            builder.row(
                InlineKeyboardButton(text="⏸ Пауза", callback_data="mail:pause"),
                InlineKeyboardButton(text="⏹ Остановить", callback_data="mail:stop")
            )
        builder.row(InlineKeyboardButton(text="🔄 Обновить статус", callback_data="mail:refresh"))
    else:
        builder.row(
            InlineKeyboardButton(text="🚀 Запустить рассылку", callback_data="mail:start_wizard"),
            InlineKeyboardButton(text="⏰ Запланировать", callback_data="mail:schedule_wizard")
        )
        builder.row(
            InlineKeyboardButton(text="📄 Скачать лог (TXT)", callback_data="stats:export_txt"),
            InlineKeyboardButton(text="📊 Скачать лог (CSV)", callback_data="stats:export_csv")
        )

    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def select_template_for_mail_kb(templates: list[Template]) -> InlineKeyboardMarkup:
    """Выбор шаблона для старта рассылки."""
    builder = InlineKeyboardBuilder()
    for tmpl in templates:
        builder.row(InlineKeyboardButton(text=f"📝 {tmpl.name}", callback_data=f"mail:set_tmpl:{tmpl.id}"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="menu:mailing"))
    return builder.as_markup()


def select_category_for_mail_kb(categories: list[Category]) -> InlineKeyboardMarkup:
    """Выбор целевой аудитории (категории) для рассылки."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🌐 Все группы (без фильтра)", callback_data="mail:set_cat:0"))
    for cat in categories:
        builder.row(InlineKeyboardButton(text=f"📁 {cat.name}", callback_data=f"mail:set_cat:{cat.id}"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="menu:mailing"))
    return builder.as_markup()


# ==========================================
# Клавиатуры для раздела Настройки
# ==========================================

def settings_menu_kb(settings: dict[str, str]) -> InlineKeyboardMarkup:
    """Меню настроек задержек и лимитов."""
    min_d = settings.get("min_delay", "30")
    max_d = settings.get("max_delay", "90")
    acc_d = settings.get("account_delay", "15")
    limit = settings.get("daily_limit_per_account", "50")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"⏱ Мин. задержка: {min_d}с", callback_data="set:min_delay"),
        InlineKeyboardButton(text=f"⏱ Макс. задержка: {max_d}с", callback_data="set:max_delay")
    )
    builder.row(
        InlineKeyboardButton(text=f"🔄 Пауза аккаунтов: {acc_d}с", callback_data="set:account_delay"),
        InlineKeyboardButton(text=f"📊 Лимит на аккаунт/сут: {limit}", callback_data="set:daily_limit")
    )
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


# ==========================================
# Клавиатуры для раздела Статистика
# ==========================================

def stats_menu_kb() -> InlineKeyboardMarkup:
    """Меню раздела статистики."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📄 Экспорт TXT", callback_data="stats:export_txt"),
        InlineKeyboardButton(text="📊 Экспорт CSV", callback_data="stats:export_csv")
    )
    builder.row(InlineKeyboardButton(text="🗑 Очистить логи", callback_data="stats:clear_ask"))
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main"))
    return builder.as_markup()
