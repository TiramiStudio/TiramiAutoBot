"""
Состояния машины состояний (FSM) для всех сценариев работы бота.
"""

from aiogram.fsm.state import State, StatesGroup


class AccountStates(StatesGroup):
    """Состояния для добавления и авторизации аккаунта Telethon."""
    enter_phone = State()
    enter_custom_api = State()
    enter_code = State()
    enter_password = State()


class GroupStates(StatesGroup):
    """Состояния для управления группами и категориями."""
    enter_targets = State()
    enter_category_name = State()
    select_category_for_groups = State()
    enter_cooldown = State()


class TemplateStates(StatesGroup):
    """Состояния для создания и редактирования шаблонов сообщений."""
    enter_name = State()
    enter_content = State()


class MailingStates(StatesGroup):
    """Состояния для настройки и запуска рассылки."""
    select_template = State()
    select_category = State()
    enter_schedule_datetime = State()
    confirm_start = State()


class SettingStates(StatesGroup):
    """Состояния для изменения настроек бота."""
    enter_min_delay = State()
    enter_max_delay = State()
    enter_account_delay = State()
    enter_cycle_delay = State()
    enter_daily_limit = State()
