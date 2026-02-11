# ghostchat_bot

## RU
Анонимный Telegram-чат на **aiogram v3**: поиск собеседника, анонимная пересылка сообщений, жалобы и админ-инструменты.

### Возможности
- `/start` с главным меню
- Поиск собеседника (очередь)
- Поиск по интересам
- Smart-матчинг: избегает повторных пар, мягко расширяет критерии, показывает примерный ETA
- Premium (несколько интересов, режим "только с интересом")
- Пробный период и промокоды
- Пропуск собеседника с cooldown
- Завершение диалога
- Оценка после чата (👍/👎) и репутация
- Профиль пользователя
- Жалобы и модерация
- Временные баны и муты (до даты)
- Настройки: автопоиск, фильтр контента, язык (RU/EN)

### Запуск
1. Создать и активировать виртуальное окружение:
```bash
python -m venv .venv
source .venv/bin/activate
```

2. Установить зависимости:
```bash
pip install -r requirements.txt
```

3. Подготовить `.env`:
```bash
cp .env.example .env
```
Заполнить `TOKEN`, `ADMIN_ID` (можно несколько через запятую), при необходимости `DB_PATH`, `PROMO_CODES`, `TRIAL_DAYS`.

4. Запустить бота:
```bash
python -m src.main
```

### Админ-команды
- `/admin` - админ-панель
- `/ban <user_id>` - перманентный бан
- `/unban <user_id>` - снять бан
- `/tempban <user_id> <hours>` - временный бан
- `/mute <user_id> <hours>` - выдать мут
- `/unmute <user_id>` - снять мут
- `/stats` - статистика
- `/export_stats` - экспорт статистики в CSV
- `/premium <user_id> <days>` - выдать Premium
- `/premium_clear <user_id>` - отключить Premium

### Premium
- Планы: 7/30/90 дней (Telegram Stars)
- Оплата через Telegram invoice
- Команда пробного периода: `/trial`
- Промокоды: `/promo CODE`

## EN
Anonymous Telegram chat bot on **aiogram v3** with matchmaking, message relay, reports, and admin tooling.

### Features
- `/start` with a main menu
- Partner search (queue-based)
- Interest-based search
- Smart matchmaking: avoids repeat pairs, softly expands criteria over time, shows ETA
- Premium (multiple interests, "interest-only" mode)
- Trial period and promo codes
- Skip partner with cooldown
- End chat
- Post-chat rating (👍/👎) and reputation
- User profile
- Reports and moderation
- Temporary bans and mutes (until date/time)
- Settings: auto-search, content filter, language (RU/EN)

### Run
1. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Prepare `.env`:
```bash
cp .env.example .env
```
Fill in `TOKEN`, `ADMIN_ID` (comma-separated if multiple), and optionally `DB_PATH`, `PROMO_CODES`, `TRIAL_DAYS`, `TELEGRAM_PROXY`, `TELEGRAM_TIMEOUT_SEC`.

4. Start the bot:
```bash
python -m src.main
```

### Admin Commands
- `/admin` - admin panel
- `/ban <user_id>` - permanent ban
- `/unban <user_id>` - remove ban
- `/tempban <user_id> <hours>` - temporary ban
- `/mute <user_id> <hours>` - set mute
- `/unmute <user_id>` - remove mute
- `/stats` - statistics
- `/export_stats` - export statistics to CSV
- `/premium <user_id> <days>` - grant Premium
- `/premium_clear <user_id>` - disable Premium

### Premium
- Plans: 7/30/90 days (Telegram Stars)
- Payment via Telegram invoice
- Trial command: `/trial`
- Promo codes: `/promo CODE`
