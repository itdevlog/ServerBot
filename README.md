# ServerBot

Телеграм-бот для управления парком Debian VPS с центрального сервера по SSH:
мониторинг, управление сервисами, обновления и reboot, Docker, shell и алерты.

Дизайн: `docs/superpowers/specs/2026-09-22-telegram-vps-manager-design.md`.

## Возможности

- `/servers` — список серверов с меню действий.
- `/status <id>`, `/statusall` — метрики CPU, RAM, диска, load, uptime.
- Управление сервисами: список запущенных, start/stop/restart, journalctl.
- Обновления `apt` и перезагрузка (с подтверждением).
- Docker: список контейнеров, логи, перезапуск.
- `/shell <id>` — произвольная команда после подтверждения.
- `/alerts` — просмотр и включение/выключение уведомлений по порогам.

## Безопасность

- Доступ только для Telegram-ID из `telegram.allowed_users`.
- Все опасные операции требуют подтверждения и показывают точную команду.
- Секреты хранятся в `config.yaml` только как `${ENV}`-ссылки;
  подстановка значений выполняется после разбора YAML, поэтому символы
  `:`, `#`, кавычки и переводы строк в секретах безопасны.
- Выполненные по подтверждению команды пишутся в лог (`audit: user=... server=... command=...`).
  Не выполняйте команды, содержащие секреты в открытом виде.
- Внимание: SSH-подключения выполняются с `known_hosts=None` (проверка host key
  отключена). Для продакшена настройте файл known_hosts на центральном сервере.
- SSH-пользователь должен иметь права на `systemctl`, `apt-get` и `reboot`
  (обычно root или passwordless sudo).

## Конфигурация

- `config.yaml` — инвентарь серверов и пороги алертов. Создаётся из
  `config.example.yaml`, в git не хранится. Секреты в нём — ссылки `${ENV}`.
- `bot.env` — секреты (`TG_BOT_TOKEN` и значения под `${...}` из `config.yaml`).
  Создаётся из `bot.env.example`, в git не хранится.

Бот читает `bot.env` при старте и подставляет недостающие переменные
окружения, поэтому systemd-юнит `manage.sh` работает без `EnvironmentFile`.

```bash
cp config.example.yaml config.yaml && chmod 600 config.yaml
cp bot.env.example bot.env && chmod 600 bot.env
```

### Как заполнить `config.yaml`

Вход по паролю аккаунта:

```yaml
servers:
  - id: web1
    name: "Web 1"
    host: 192.168.1.116
    port: 22
    user: root
    auth:
      type: password
      password: "${ROOT4}"
    tags: [ai, agent]
```

Вход по SSH-ключу (с парольной фразой):

```yaml
servers:
  - id: web1
    name: "Web 1"
    host: 192.168.1.116
    port: 22
    user: root
    auth:
      type: key
      key_path: "~/.ssh/id_ed25519"
      passphrase: "${ROOT4}"
    tags: [ai, agent]
```

Правила:

- `id` — уникальный, используется в командах (`/status <id>`) и кнопках;
  дубликаты запрещены.
- `auth.type` — `password` или `key`:
  - `password` — обязателен `password`;
  - `key` — обязателен `key_path`; `passphrase` нужен только если ключ
    зашифрован, иначе строку опустите.
- `key_path` раскрывает `~` в домашний каталог пользователя, под которым
  запущен бот; файл ключа должен быть ему читаем.
- Одна запись — один способ входа. «Ключ **и** пароль аккаунта»
  одновременно не поддерживается: нужен либо ключ (с passphrase), либо пароль.
- Секреты не пишите в `config.yaml` — только ссылки `${ENV}`, а значения —
  в `bot.env`.
- `tags` — произвольные метки, необязательны.

## Установка одной командой

На чистом Debian VPS (нужны `git` и доступ к репозиторию):

```bash
curl -fsSL https://raw.githubusercontent.com/itdevlog/ServerBot/master/manage.sh | bash -s -- install
```

Скрипт клонирует репозиторий в `/opt/serverbot` и запускает `install`:
venv, зависимости, systemd-юнит, автозапуск. Без терминала `bot.env`
копируется из `bot.env.example`; после установки впишите `TG_BOT_TOKEN`
и секреты серверов, создайте `config.yaml` и выполните `./manage.sh restart`.

> Репозиторий публичный, отдельная авторизация не нужна. `manage.sh`
> при необходимости сам доустановит `git` и `curl` через apt.

## Быстрый старт

Если репозиторий уже склонирован:

```bash
./manage.sh install
```

`manage.sh` создаёт venv, ставит зависимости из `requirements.txt`, пишет
systemd-юнит `serverbot-bot-<instance>` и включает автозапуск. Если токен в
`bot.env` ещё не задан, сервис включается, но не запускается.

## Управление

`manage.sh` — единая точка эксплуатации (подробнее: `./manage.sh help`):

| Команда | Назначение |
|---|---|
| `install` | venv, зависимости, systemd, автозапуск |
| `update` | обновление с GitHub + бэкап + откат при сбое |
| `doctor` | диагностика: venv, зависимости, env, сервис |
| `backup` / `restore` | бэкап `bot.env` и `config.yaml` в `backups/` |
| `start` / `stop` / `restart` / `status` | жизненный цикл сервиса |
| `logs` | логи в реальном времени |
| `uninstall` | остановка и удаление сервиса |

Несколько ботов на одном сервере: имя инстанса задаётся `--instance ИМЯ`
или переменной `SERVERBOT_INSTANCE`; каждому — свой systemd-юнит, PID и порт.

## Ручной запуск (без systemd)

```bash
.venv/bin/python run.py
```

`run.py` — тонкий лончер, добавляющий `src` в `sys.path`.

## Тесты

```bash
.venv/bin/pytest -v
```
