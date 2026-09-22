# Telegram VPS Manager

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

## Установка

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp config.example.yaml config.yaml
chmod 600 config.yaml
```

Заполните `config.yaml`: токен бота, свой Telegram-ID, список серверов.
Секретные значения задайте переменными окружения (`TG_BOT_TOKEN`,
`WEB1_PASS`, `DB1_PASSPHRASE`).

## Запуск

```bash
export TG_BOT_TOKEN=...
export WEB1_PASS=...
export DB1_PASSPHRASE=...
python -m bot.main
```

## Тесты

```bash
pytest -v
```

## Деплой через systemd

```bash
sudo useradd --system --home /opt/management --create-home management
sudo mkdir -p /opt/management
sudo cp -r src pyproject.toml config.example.yaml /opt/management/
sudo cp config.yaml /opt/management/
sudo cp deploy/management-bot.service /etc/systemd/system/
sudo chown -R management:management /opt/management
sudo chmod 600 /opt/management/config.yaml
sudo -u management python3.11 -m venv /opt/management/.venv
sudo -u management /opt/management/.venv/bin/pip install /opt/management
sudo tee /opt/management/bot.env >/dev/null <<'EOF'
TG_BOT_TOKEN=...
WEB1_PASS=...
DB1_PASSPHRASE=...
EOF
sudo chown management:management /opt/management/bot.env
sudo chmod 600 /opt/management/bot.env
sudo systemctl daemon-reload
sudo systemctl enable --now management-bot
```

`/opt/management/bot.env` — файл с секретами в формате `KEY=value`
(`TG_BOT_TOKEN`, `WEB1_PASS`, `DB1_PASSPHRASE`), владелец `management`,
права `chmod 600`. Юнит читает его через `EnvironmentFile`. Файлы
`/opt/management` принадлежат пользователю `management`, поэтому сервис
под `User=management` может читать `config.yaml` и `bot.env`.
