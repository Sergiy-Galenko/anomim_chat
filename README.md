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
- Настройки: автопоиск, фильтр контента, язык (RU/EN/UK/DE)

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
Заполнить `TOKEN`, `ADMIN_ID` (можно несколько через запятую), при необходимости `DB_PATH`, `DATABASE_URL`, `REDIS_URL`, `PROMO_CODES`, `TRIAL_DAYS`.

- `DB_PATH` - путь к SQLite-файлу для локального запуска.
- `DATABASE_URL` - PostgreSQL DSN для production, например `postgresql://user:pass@host:5432/dbname`.
- `REDIS_URL` - Redis для FSM storage в production. Если не задан, используется in-memory storage.

4. Запустить бота:
```bash
python -m src.main
```

### Миграции БД
- Схема теперь поддерживается версионируемыми миграциями в `src/db/migrations.py`.
- При старте `Database.connect()` автоматически создаёт `schema_migrations` и применяет недостающие миграции для SQLite и PostgreSQL.
- Для существующих SQLite/PostgreSQL баз ручные `ALTER TABLE` больше не спрятаны в коде подключения: изменения схемы должны добавляться как новая миграция.

### Deploy on Vercel
- В репозиторий добавлен Vercel-совместимый Python webhook-handler в `api/index.py`.
- В настройках проекта на Vercel нужно задать `TOKEN`, `ADMIN_ID`, а при необходимости `DATABASE_URL`, `REDIS_URL`, `TELEGRAM_WEBHOOK_SECRET`, `PROMO_CODES`, `TRIAL_DAYS`, `TELEGRAM_TIMEOUT_SEC`, `TELEGRAM_PROXY`.
- Если `DB_PATH` на Vercel не задан, приложение автоматически использует `/tmp/ghostchat.db`, чтобы деплой мог запуститься.
- Важно: `/tmp` на Vercel эфемерен. Бот сможет собираться и принимать апдейты, но данные SQLite будут теряться при cold start и смене инстанса. Для production нужен внешний persistent DB.
- Для production теперь предусмотрен PostgreSQL через `DATABASE_URL` и Redis FSM storage через `REDIS_URL`.
- После деплоя установите webhook на `https://<your-project>.vercel.app/api`. Если используете `TELEGRAM_WEBHOOK_SECRET`, передайте то же значение как `secret_token`.

Пример:
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<your-project>.vercel.app/api" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
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

### Tests
```bash
python3 -m unittest discover -s tests -v
```

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
- Settings: auto-search, content filter, language (RU/EN/UK/DE)

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
Fill in `TOKEN`, `ADMIN_ID` (comma-separated if multiple), and optionally `DB_PATH`, `DATABASE_URL`, `REDIS_URL`, `PROMO_CODES`, `TRIAL_DAYS`, `TELEGRAM_PROXY`, `TELEGRAM_TIMEOUT_SEC`.
If `TELEGRAM_PROXY` is empty, the bot also tries system proxy vars (`ALL_PROXY`, `HTTPS_PROXY`, `HTTP_PROXY`).

- `DB_PATH` - SQLite file path for local/dev runs.
- `DATABASE_URL` - PostgreSQL DSN for production.
- `REDIS_URL` - Redis URL for durable FSM storage in production. If omitted, in-memory FSM storage is used.

4. Start the bot:
```bash
python -m src.main
```

### DB Migrations
- The schema is now managed by versioned migrations in `src/db/migrations.py`.
- On startup, `Database.connect()` creates `schema_migrations` and applies any pending migrations for both SQLite and PostgreSQL.
- Existing SQLite/PostgreSQL deployments no longer rely on hidden `ALTER TABLE` logic in the connection path; new schema changes should be added as a new migration.

### Deploy on Vercel
- The repo now includes a Vercel-compatible Python webhook function in `api/index.py`.
- Add `TOKEN`, `ADMIN_ID`, and optionally `DATABASE_URL`, `REDIS_URL`, `TELEGRAM_WEBHOOK_SECRET`, `PROMO_CODES`, `TRIAL_DAYS`, `TELEGRAM_TIMEOUT_SEC`, `TELEGRAM_PROXY` in Vercel Project Settings.
- If `DB_PATH` is not set on Vercel, the app falls back to `/tmp/ghostchat.db` so the deployment can boot.
- Important: `/tmp` is ephemeral on Vercel. The bot can build and receive updates, but SQLite data will be lost across cold starts and instance changes. Use an external database before treating Vercel as production hosting.
- The project now supports PostgreSQL via `DATABASE_URL` and Redis-backed FSM via `REDIS_URL` for production-ready deployments.
- Point Telegram webhook to `https://<your-project>.vercel.app/api`. If you set `TELEGRAM_WEBHOOK_SECRET`, use the same value in Telegram webhook setup.

Example:
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<your-project>.vercel.app/api" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

### Troubleshooting
- `git pull` fails with `__pycache__` conflicts:
```bash
find src -type d -name "__pycache__" -prune -exec rm -rf {} +
find src -type f -name "*.pyc" -delete
git pull
```
- `Cannot connect to host api.telegram.org:443`:
  set `TELEGRAM_PROXY` in `.env` (or use `ALL_PROXY` / `HTTPS_PROXY` / `HTTP_PROXY`).

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

### Tests
```bash
python3 -m unittest discover -s tests -v
```
