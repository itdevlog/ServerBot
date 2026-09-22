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

## Быстрый старт

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
