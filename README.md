<div align="center">

# 🍰 TiramiAutoBot

### *Профессиональный Telegram-бот для умной авторассылки сообщений*
**Разработано студией [TiramiStudio](https://t.me/tiramistudio)**

[![Telegram Channel](https://img.shields.io/badge/Telegram-TiramiStudio-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/tiramistudio)
[![Discord Server](https://img.shields.io/badge/Discord-Join%20Community-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/BcQEwxhT45)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![Telethon](https://img.shields.io/badge/Telethon-1.34%2B-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://docs.telethon.dev/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20%2F%20aiosqlite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://github.com/omnilib/aiosqlite)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[Возможности](#-ключевые-возможности) •
[Стек технологий](#-стек-технологий) •
[Установка и запуск](#-установка-и-запуск) •
[Конфигурация](#-конфигурация-env) •
[Инструкция](#-инструкция-по-использованию) •
[Контакты и сообщество](#-сообщество-и-поддержка)

---

</div>

## 📌 О проекте

**TiramiAutoBot** — это мощный асинхронный инструмент для автоматизированного распространения сообщений в Telegram-группах и супергруппах. Бот создан студией **TiramiStudio** с упором на надежность, безопасность аккаунтов, гибкую рандомизацию контента и удобный графический интерфейс на inline-кнопках.

---

## 🌟 Ключевые возможности

### 📱 1. Мультиаккаунтинг и сессии
- **Авторизация внутри бота:** Подключение Telegram-аккаунтов по номеру телефона через интерактивный диалог (Telethon).
- **Поддержка 2FA:** Корректная обработка облачного пароля двухфакторной аутентификации.
- **Статусы аккаунтов:** Мониторинг состояния (🟢 *Активен*, 🟡 *FloodWait*, 🔴 *Заблокирован / Ошибка*).
- **Массовая проверка:** Быстрая валидация всех сессий в один клик.

### 👥 2. Управление целевыми группами
- **Ручное добавление:** Построчный ввод списка групп (`@username`, ссылки `t.me/...`, приватные ссылки-инвайты `t.me/+hash`, ID чатов).
- **Автопарсинг диалогов:** Выгрузка всех групп и супергрупп прямо с подключенного аккаунта.
- **Категории и теги:** Группировка чатов по тематикам для сегментированной рассылки.
- **Удобная пагинация:** Просмотр базы групп постранично с возможностью быстрого удаления.

### 📝 3. Шаблоны сообщений и Спинтакс
- **Мультимедиа:** Поддержка текста, фотографий, видео и документов.
- **Форматирование:** HTML-разметка (`<b>жирный</b>`, `<i>курсив</i>`, `<code>код</code>`, ссылки).
- **Многоуровневый Спинтакс:** Рандомизация фраз любой глубины:  
  `{Привет|Здравствуйте {уважаемый|дорогой}|Доброго времени суток}`.
- **Предпросмотр:** Тестовая генерация вариантов текста перед стартом.

### 🛡 4. Продвинутая защита от блокировок (Антибан)
- **Случайные задержки (Cooldown):** Рандомизированные паузы между отправками (например, от 30 до 90 сек).
- **Ротация сессий:** Поочередная отправка с разных аккаунтов с дополнительной паузой переключения.
- **Дневные лимиты:** Ограничение числа сообщений на каждый аккаунт за 24 часа.
- **Автообработка FloodWait:** Перехват `FloodWaitError` и плавный переход к следующему свободному аккаунту.
- **Умный пропуск:** Изоляция чатов с запретом на отправку (`ChatWriteForbiddenError`, `UserBannedInChannelError`).

### 🚀 5. Управление рассылкой и аналитика
- **Живой монитор прогресса:** Интерактивное табло со шкалой выполнения `[████░░░░░░] 40%`, счетчиками и таймером.
- **Управление на лету:** Мгновенная **пауза**, **возобновление** и **остановка**.
- **Планировщик задач:** Отложенный запуск на определенное время через `APScheduler`.
- **Экспорт отчетов:** Скачивание журнала отправки в форматах `.CSV` и `.TXT`.

---

## 🛠 Стек технологий

- **Язык разработки:** Python 3.11+
- **Telegram Bot API:** [aiogram 3.x](https://github.com/aiogram/aiogram)
- **Telegram MTProto Client:** [Telethon](https://github.com/LonamiWebs/Telethon)
- **База данных:** SQLite через [aiosqlite](https://github.com/omnilib/aiosqlite)
- **Планировщик:** [APScheduler](https://github.com/agronholm/apscheduler)
- **Конфигурация:** [python-dotenv](https://github.com/theskumar/python-dotenv)

---

## 📂 Структура проекта

```text
burmaldabot/
├── bot/
│   ├── __init__.py
│   ├── main.py                  # Главная точка входа TiramiAutoBot
│   ├── config.py                # Конфигурация и валидация .env
│   ├── database/
│   │   ├── __init__.py
│   │   ├── db.py                # Асинхронные методы базы данных SQLite
│   │   └── models.py            # Модели сущностей (Account, Group, Template и др.)
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── common.py            # Главное меню, контакты TiramiStudio, статистика
│   │   ├── accounts.py          # Авторизация Telethon, ввод кодов, 2FA
│   │   ├── groups.py            # Управление группами, парсинг, категории
│   │   ├── templates.py         # Шаблоны, спинтакс, медиа
│   │   ├── mailing.py           # Мастер рассылки, живой монитор, планировщик
│   │   └── settings.py          # Настройка интервалов и лимитов
│   ├── services/
│   │   ├── __init__.py
│   │   ├── telethon_manager.py  # Управление клиентами и отправка сообщений
│   │   ├── mailing_service.py   # Движок рассылки, ротация, антибан
│   │   └── spintax.py           # Парсер и генератор спинтакса
│   ├── keyboards/
│   │   ├── __init__.py
│   │   └── inline.py            # Инлайн-клавиатуры и социальные ссылки
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py           # Прогресс-бар, нормализация ссылок, экспорт логов
│       └── states.py            # FSM-состояния aiogram
├── data/                        # Хранилище базы данных SQLite
├── sessions/                    # Файлы сессий Telethon (.session)
├── media/                       # Сохраненные медиафайлы шаблонов
├── .env.example                 # Шаблон переменных окружения
├── requirements.txt             # Зависимости Python
└── README.md                    # Документация проекта
```

---

## 🚀 Установка и запуск

### 1. Клонирование репозитория
```bash
git clone https://github.com/your-username/TiramiAutoBot.git
cd TiramiAutoBot
```

### 2. Создание и активация виртуального окружения
- **Linux / macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```
- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```

### 3. Установка зависимостей
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Конфигурация (.env)
Скопируйте пример файла конфигурации:
```bash
cp .env.example .env
```
Заполните `.env` своими данными:
```env
# Токен бота (получить у @BotFather)
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Числовой ID администратора (узнать в @userinfobot)
ADMIN_IDS=123456789

# Telegram API ID и Hash (получить на https://my.telegram.org)
DEFAULT_API_ID=12345678
DEFAULT_API_HASH=0123456789abcdef0123456789abcdef
```

### 5. Запуск бота
```bash
python -m bot.main
```

---

## 📖 Инструкция по использованию

1. **Подключение аккаунтов:** Откройте **📱 Аккаунты** ➡️ **➕ Добавить аккаунт**, введите номер телефона, код подтверждения и 2FA пароль (если включен).
2. **Наполнение групп:** Откройте **👥 Группы** ➡️ спарсите группы с аккаунта (**📥 Спарсить с аккаунта**) или вставьте список ссылок вручную (**➕ Добавить вручную**).
3. **Создание шаблона:** Перейдите в **📝 Шаблоны** ➡️ **➕ Создать шаблон**, отправьте текст со спинтаксом и медиа (при необходимости).
4. **Старт рассылки:** Нажмите **🚀 Рассылка** ➡️ **🚀 Запустить рассылку**, выберите шаблон, категорию и подтвердите запуск. Следите за прогрессом через интерактивное меню!

---

## 🌐 Сообщество и поддержка

Присоединяйтесь к сообществу студии **TiramiStudio**:

- 📢 **Telegram-канал:** [t.me/tiramistudio](https://t.me/tiramistudio)
- 💬 **Discord-сервер:** [discord.gg/BcQEwxhT45](https://discord.gg/BcQEwxhT45)

---

## 📄 Лицензия

Проект разработан **TiramiStudio** и распространяется под лицензией [MIT](LICENSE).

<div align="center">
  <sub>© 2026 TiramiStudio. Все права защищены.</sub>
</div>
