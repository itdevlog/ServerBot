# Telegram-бот для управления Debian VPS — дизайн

Дата: 2026-09-22

## Цель

Личный инструмент в Telegram для управления парком Debian VPS с одного
центрального сервера: мониторинг, управление сервисами, обновления и
reboot, Docker, произвольные shell-команды, алерты.

## Область (scope)

Входит в MVP:

- Центральный бот, подключается к нескольким VPS по SSH.
- Мониторинг метрик и статуса.
- Управление сервисами (`systemctl`), логи (`journalctl`).
- Обновления (`apt`) и reboot.
- Docker (список, старт/стоп/рестарт, логи, статистика).
- Произвольные shell-команды.
- Алерты по порогам.

Не входит в MVP:

- Динамическое добавление серверов через бота (только `config.yaml`).
- Мультипользовательность и роли (только whitelist одного/нескольких ID).
- Веб-интерфейс.
- Хранение истории метрик в БД (состояние алертов — in-memory).

## Решения (зафиксировано)

| Вопрос | Решение |
|---|---|
| Топология | Один бот на центральном сервере, управляет многими VPS по SSH |
| Функционал | Мониторинг, сервисы, обновления/reboot, Docker, shell, алерты |
| Доступ | Whitelist Telegram user ID |
| Стек | Python: aiogram 3 + asyncssh + APScheduler |
| Инвентарь | Статичный `config.yaml` |
| Авторизация SSH | Оба варианта: логин+пароль и ключ с passphrase |
| Состояние алертов | In-memory (без SQLite) |
| Подход | Модульный монолит (вариант A) |

## Архитектура

```
Telegram ──► aiogram handlers
                  │
                  ▼
          action/collector layer
                  │
                  ▼
             ssh pool (asyncssh)
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
    server1    server2    serverN   (Debian VPS)

APScheduler ──► collectors ──► alerts ──► bot.send_message(whitelist)
config.yaml   (инвентарь, SSH-доступы, пороги)
```

Компоненты (один модуль — одна ответственность):

- **`config`** — парсинг/валидация `config.yaml` через pydantic;
  подстановка `${ENV}`; поддержка auth `password` и `key`+`passphrase`.
- **`ssh`** — пул асинхронных SSH-подключений, `run(server, cmd)`,
  таймауты, реконнект, параллельный запуск, пометка offline.
- **`collectors`** — сбор метрик парсингом вывода утилит; каждый
  коллектор — чистая функция `raw -> dataclass`.
- **`actions`** — операции (services, updates, docker, shell); каждое
  действие имеет описание, признак риска и требует подтверждения.
- **`alerts`** — пороги, edge-trigger (enter/resolve), cooldown,
  in-memory состояние.
- **`handlers`** — aiogram: команды, инлайн-кнопки, FSM для shell.
- **`security`** — whitelist-middleware, хранилище подтверждений с TTL.
- **`main`** — сборка зависимостей, запуск бота и планировщика,
  graceful shutdown.

## Интерфейс Telegram

| Команда | Действие |
|---|---|
| `/start`, `/help` | справка |
| `/servers` | список серверов (инлайн-кнопки) со статусом online/offline |
| `/status` | метрики выбранного сервера |
| `/statusall` | сводка по всем серверам |
| `/alerts` | вкл/выкл уведомления, пороги |
| `/shell <server>` | запуск FSM ввода команды |

Меню сервера (callback `action:server_id`):
`📊 Метрики` · `⚙️ Сервисы` · `📦 Обновления` · `🐳 Docker` · `💻 Shell` · `📜 Логи` · `🔄 Reboot`.

Поток опасных операций (stop/restart, reboot, apt upgrade, shell):

1. Бот показывает точную команду, которую выполнит.
2. Инлайн-кнопки `✅ Подтвердить` / `❌ Отмена`, TTL 60 сек,
   подтверждение привязано к user ID.
3. Вывод команды (stdout/stderr, обрезка до `output_max_lines`),
   код возврата, длительность.
4. Просроченные/чужие подтверждения отклоняются.

## Конфигурация

`config.yaml` (права `600`), секреты через `${ENV}`:

```yaml
telegram:
  token: "${TG_BOT_TOKEN}"
  allowed_users: [123456789]

defaults:
  ssh: { connect_timeout: 10, command_timeout: 30, max_concurrency: 8 }
  output_max_lines: 40

alerts:
  enabled: true
  interval: 60
  cooldown: 300
  thresholds:
    cpu_percent: 85
    ram_percent: 90
    disk_percent: 85
    load_per_cpu: 2.0
    offline: true

servers:
  - id: web1
    name: "Web 1"
    host: 1.2.3.4
    port: 22
    user: admin
    auth: { type: password, password: "${WEB1_PASS}" }
    tags: [web, prod]
  - id: db1
    name: "DB 1"
    host: 5.6.7.8
    user: deploy
    auth: { type: key, key_path: "~/.ssh/db1", passphrase: "${DB1_PASSPHRASE}" }
    tags: [db, prod]
```

## Потоки данных

**Метрики по запросу:** handler → `collectors` (через `ssh.run`) →
dataclass → форматирование → ответ в Telegram.

**Алерты:** APScheduler раз в `interval` → параллельный опрос серверов
(`asyncio.gather(..., return_exceptions=True)`) → `alerts` сравнивает с
порогами → edge-trigger → cooldown → сообщение в whitelist.

## Обработка ошибок

- Каждое SSH-действие — с таймаутом и try/except; при неудаче сервер
  помечается `offline`, бот отвечает понятным текстом, процесс живёт.
- Вывод обрезается до `output_max_lines` с пометкой об усечении.
- Недоступность одного сервера не ломает опрос остальных.

## Безопасность

- Middleware: не-whitelist пользователи игнорируются молча, попытки
  логируются.
- Опасные операции — только через подтверждение с показом команды.
- Секреты не пишутся в логи; в конфиге — через `${ENV}`.
- Параметры (имя сервиса/контейнера) валидируются и экранируются —
  произвольный ввод не подставляется в shell.
- `/shell` доступен только whitelist; выполняется под SSH-пользователем.

## Тестирование

pytest + pytest-asyncio, без обращения к реальным VPS (SSH замокан):

- `test_collectors` — парсинг фикстур (`top`, `df`, `systemctl`,
  `docker ps`).
- `test_alerts` — переходы порог/resolve, cooldown, edge-trigger.
- `test_actions` — формирование команд, обрезка вывода, экранирование.
- `test_config` — парсинг, `${ENV}`, валидация auth-вариантов.

## Деплой

`systemd`-юнит на центральном сервере: venv, `EnvironmentFile` с
секретами, рестарт при падении, логи в journald, автозапуск при загрузке.

## Структура проекта

```
management/
├── pyproject.toml
├── config.example.yaml
├── README.md
├── deploy/management-bot.service
├── src/bot/
│   ├── main.py
│   ├── config.py
│   ├── security.py
│   ├── keyboards.py
│   ├── ssh/pool.py
│   ├── collectors/system.py, docker.py
│   ├── actions/services.py, updates.py, docker.py, shell.py
│   ├── alerts/engine.py
│   └── handlers/start.py, servers.py, status.py, services.py,
│                updates.py, docker.py, shell.py, alerts.py
└── tests/
    ├── fixtures/
    └── test_collectors.py, test_alerts.py, test_actions.py, test_config.py
```
