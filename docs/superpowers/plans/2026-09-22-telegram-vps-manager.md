# Telegram VPS Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telegram-бот на Python, который с центрального сервера управляет парком Debian VPS по SSH: мониторинг, сервисы, обновления/reboot, Docker, shell и алерты.

**Architecture:** Модульный монолит. aiogram 3 принимает команды, `SshPool` (asyncssh) выполняет команды на серверах, коллекторы парсят вывод, `AlertEngine` в памяти отслеживает пороги, APScheduler периодически опрашивает серверы. Инвентарь — `config.yaml` с `${ENV}`-подстановкой.

**Tech Stack:** Python 3.11+, aiogram 3.13+, asyncssh 2.17+, pydantic 2.7+, PyYAML, APScheduler 3.10+, pytest, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-09-22-telegram-vps-manager-design.md`

## Global Constraints

- Python ≥ 3.11.
- Зависимости: `aiogram>=3.13,<4`, `asyncssh>=2.17`, `pydantic>=2.7`, `PyYAML>=6.0`, `APScheduler>=3.10,<4`; dev: `pytest>=8`, `pytest-asyncio>=0.23`.
- Название пакета: `bot`, исходники в `src/`, тесты в `tests/`.
- В коде **не писать комментарии**.
- Секреты только через `${ENV}` в конфиге, никогда не логировать.
- Вывод команд обрезать до `defaults.output_max_lines`.
- Тесты полностью офлайновые: SSH всегда замокан, реальные VPS не трогаем.
- Пакет данных для Telegram: статические сообщения — `parse_mode="HTML"` с экранированием, вывод команд — экранировать через `html.escape`.
- Длительность тестов: каждый шаг ≤ 5 минут.
- Коммит после каждого зелёного шага; сообщения в стиле Conventional Commits.

## File Structure

```
management/
├── pyproject.toml                     # пакет, зависимости, pytest config
├── config.example.yaml                # пример конфига
├── README.md                          # запуск, деплой, безопасность
├── deploy/management-bot.service      # systemd unit
├── src/bot/
│   ├── __init__.py
│   ├── config.py                      # pydantic-схема, ${ENV}, load_config
│   ├── security.py                    # WhitelistMiddleware, ConfirmationStore
│   ├── keyboards.py                   # инлайн-клавиатуры
│   ├── formatting.py                  # форматирование сообщений, truncate
│   ├── ssh/__init__.py
│   ├── ssh/pool.py                    # SshPool, ServerUnavailable, CommandResult
│   ├── collectors/__init__.py
│   ├── collectors/system.py           # SystemMetrics, parse, collect
│   ├── collectors/docker.py           # ContainerInfo, parse, collect
│   ├── actions/__init__.py
│   ├── actions/base.py                # PreparedAction, InvalidArgument, validate_token
│   ├── actions/services.py            # unit validation, systemctl
│   ├── actions/updates.py             # apt, reboot
│   ├── actions/docker.py              # docker restart/logs
│   ├── actions/shell.py               # shell_action
│   ├── alerts/__init__.py
│   ├── alerts/engine.py               # AlertEvent, AlertEngine, AlertRuntime
│   ├── handlers/__init__.py
│   ├── handlers/common.py             # DependenciesMiddleware, states, execute
│   ├── handlers/start.py              # /start /help
│   ├── handlers/servers.py            # /servers /statusall
│   ├── handlers/status.py             # /status, metrics callback
│   ├── handlers/services.py           # units list + unit actions + logs
│   ├── handlers/updates.py            # updates check/upgrade/reboot
│   ├── handlers/docker.py             # docker list/restart/logs
│   ├── handlers/shell.py              # /shell FSM
│   ├── handlers/alerts.py             # /alerts
│   └── handlers/confirm.py            # confirm/cancel callbacks
│   └── main.py                        # сборка, scheduler, polling
└── tests/
    ├── __init__.py
    ├── conftest.py                    # sample_server
    ├── fixtures/system_output.txt
    ├── fixtures/docker_ps.txt
    ├── fixtures/systemctl_units.txt
    ├── fixtures/apt_upgradable.txt
    ├── test_smoke.py
    ├── test_config.py
    ├── test_ssh_pool.py
    ├── test_collectors_system.py
    ├── test_collectors_docker.py
    ├── test_actions.py
    ├── test_security.py
    ├── test_alerts.py
    └── test_formatting.py
```

---

### Task 1: Scaffolding and test setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/bot/__init__.py`
- Create: `tests/__init__.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: importable package `bot`; `pytest` runs with `pythonpath=["src"]`.

- [ ] **Step 1: Write the failing test**

`tests/test_smoke.py`:

```python
def test_package_importable():
    import bot

    assert bot.__name__ == "bot"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot' or config missing)

- [ ] **Step 3: Create package files**

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "vps-manager-bot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "aiogram>=3.13,<4",
    "asyncssh>=2.17",
    "pydantic>=2.7",
    "PyYAML>=6.0",
    "APScheduler>=3.10,<4",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`src/bot/__init__.py`:

```python
__version__ = "0.1.0"
```

`tests/__init__.py`: empty file.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/bot/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold python package and test setup"
```

---

### Task 2: Config loading with env substitution

**Files:**
- Create: `src/bot/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ConfigError(Exception)`
  - `expand_env(text: str, env: Mapping[str, str] | None = None) -> str`
  - pydantic models: `SshAuth`, `ServerConfig`, `SshDefaults`, `Defaults`, `Thresholds`, `AlertsConfig`, `TelegramConfig`, `AppConfig`
  - `AppConfig.server(server_id: str) -> ServerConfig | None`
  - `load_config(path: str | Path, env: Mapping[str, str] | None = None) -> AppConfig`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:

```python
from pathlib import Path

import pytest

from bot.config import AppConfig, ConfigError, expand_env, load_config

VALID = """
telegram:
  token: "${TG_TOKEN}"
  allowed_users: [42]
servers:
  - id: web1
    name: "Web 1"
    host: 1.2.3.4
    user: admin
    auth: { type: password, password: "${WEB_PASS}" }
  - id: db1
    name: "DB 1"
    host: 5.6.7.8
    user: deploy
    auth: { type: key, key_path: "~/.ssh/db1", passphrase: "${DB_PASS}" }
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_expand_env_substitutes_known_variable():
    assert expand_env("a=${X}", {"X": "1"}) == "a=1"


def test_expand_env_raises_on_missing_variable():
    with pytest.raises(ConfigError, match="MISSING"):
        expand_env("${MISSING}", {})


def test_load_config_full(tmp_path):
    env = {"TG_TOKEN": "t", "WEB_PASS": "p", "DB_PASS": "k"}
    config = load_config(write(tmp_path, VALID), env)

    assert isinstance(config, AppConfig)
    assert config.telegram.token == "t"
    assert config.telegram.allowed_users == [42]
    assert config.server("web1").auth.password == "p"
    assert config.server("db1").auth.key_path == "~/.ssh/db1"
    assert config.server("db1").auth.passphrase == "k"
    assert config.server("missing") is None
    assert config.defaults.output_max_lines == 40
    assert config.alerts.thresholds.cpu_percent == 85.0


def test_password_auth_requires_password(tmp_path):
    text = """
telegram: { token: t, allowed_users: [1] }
servers:
  - id: a
    name: a
    host: h
    user: u
    auth: { type: password }
"""
    with pytest.raises(ValueError, match="password"):
        load_config(write(tmp_path, text), {})


def test_key_auth_requires_key_path(tmp_path):
    text = """
telegram: { token: t, allowed_users: [1] }
servers:
  - id: a
    name: a
    host: h
    user: u
    auth: { type: key }
"""
    with pytest.raises(ValueError, match="key_path"):
        load_config(write(tmp_path, text), {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.config')

- [ ] **Step 3: Write implementation**

`src/bot/config.py`:

```python
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal, Mapping

import yaml
from pydantic import BaseModel, Field, model_validator

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(Exception):
    pass


def expand_env(text: str, env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in source:
            raise ConfigError(f"Missing environment variable: {name}")
        return source[name]

    return _ENV_RE.sub(replace, text)


class SshAuth(BaseModel):
    type: Literal["password", "key"]
    password: str | None = None
    key_path: str | None = None
    passphrase: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "SshAuth":
        if self.type == "password" and not self.password:
            raise ValueError("password auth requires 'password'")
        if self.type == "key" and not self.key_path:
            raise ValueError("key auth requires 'key_path'")
        return self


class ServerConfig(BaseModel):
    id: str
    name: str
    host: str
    port: int = 22
    user: str
    auth: SshAuth
    tags: list[str] = Field(default_factory=list)


class SshDefaults(BaseModel):
    connect_timeout: int = 10
    command_timeout: int = 30
    max_concurrency: int = 8


class Defaults(BaseModel):
    ssh: SshDefaults = Field(default_factory=SshDefaults)
    output_max_lines: int = 40


class Thresholds(BaseModel):
    cpu_percent: float = 85.0
    ram_percent: float = 90.0
    disk_percent: float = 85.0
    load_per_cpu: float = 2.0
    offline: bool = True


class AlertsConfig(BaseModel):
    enabled: bool = True
    interval: int = 60
    cooldown: int = 300
    thresholds: Thresholds = Field(default_factory=Thresholds)


class TelegramConfig(BaseModel):
    token: str
    allowed_users: list[int]


class AppConfig(BaseModel):
    telegram: TelegramConfig
    defaults: Defaults = Field(default_factory=Defaults)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    servers: list[ServerConfig]

    def server(self, server_id: str) -> ServerConfig | None:
        for server in self.servers:
            if server.id == server_id:
                return server
        return None


def load_config(path: str | Path, env: Mapping[str, str] | None = None) -> AppConfig:
    raw = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(expand_env(raw, env))
    return AppConfig.model_validate(data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/bot/config.py tests/test_config.py
git commit -m "feat: add config schema with env substitution"
```

---

### Task 3: SSH pool

**Files:**
- Create: `src/bot/ssh/__init__.py`
- Create: `src/bot/ssh/pool.py`
- Test: `tests/test_ssh_pool.py`

**Interfaces:**
- Consumes: `ServerConfig`, `SshDefaults` from `bot.config`.
- Produces:
  - `ServerUnavailable(Exception)`
  - `CommandResult` dataclass: `stdout: str`, `stderr: str`, `exit_status: int`, `duration: float`
  - `SshPool(defaults: SshDefaults)`, methods `async run(server, command, timeout=None) -> CommandResult`, `async aclose() -> None`

- [ ] **Step 1: Write the failing test**

`tests/test_ssh_pool.py`:

```python
import asyncssh
import pytest

from bot.config import ServerConfig, SshDefaults
from bot.ssh.pool import CommandResult, ServerUnavailable, SshPool


def make_server(server_id: str = "web1") -> ServerConfig:
    return ServerConfig(
        id=server_id,
        name="Web 1",
        host="1.2.3.4",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


class FakeResult:
    def __init__(self, stdout: str, stderr: str, exit_status: int):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_status = exit_status


class FakeConn:
    def __init__(self):
        self.closed = False
        self.commands: list[str] = []

    async def run(self, command: str, check: bool = False) -> FakeResult:
        self.commands.append(command)
        return FakeResult("ok", "", 0)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


async def test_run_returns_command_result(monkeypatch):
    conn = FakeConn()

    async def fake_connect(**kwargs):
        return conn

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())
    result = await pool.run(make_server(), "echo ok")

    assert result == CommandResult("ok", "", 0, result.duration)
    assert result.exit_status == 0
    assert conn.commands == ["echo ok"]


async def test_connection_is_cached(monkeypatch):
    conn = FakeConn()
    calls = 0

    async def fake_connect(**kwargs):
        nonlocal calls
        calls += 1
        return conn

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())
    await pool.run(make_server(), "a")
    await pool.run(make_server(), "b")

    assert calls == 1


async def test_connection_error_raises_server_unavailable(monkeypatch):
    async def fake_connect(**kwargs):
        raise OSError("boom")

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())

    with pytest.raises(ServerUnavailable, match="boom"):
        await pool.run(make_server(), "x")


async def test_password_auth_passes_password(monkeypatch):
    captured = {}

    async def fake_connect(**kwargs):
        captured.update(kwargs)
        return FakeConn()

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())
    await pool.run(make_server(), "x")

    assert captured["password"] == "secret"
    assert captured["host"] == "1.2.3.4"
    assert captured["username"] == "admin"


async def test_key_auth_passes_client_keys(monkeypatch):
    captured = {}

    async def fake_connect(**kwargs):
        captured.update(kwargs)
        return FakeConn()

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())
    server = ServerConfig(
        id="db1",
        name="DB 1",
        host="5.6.7.8",
        user="deploy",
        auth={"type": "key", "key_path": "~/.ssh/db1", "passphrase": "k"},
    )
    await pool.run(server, "x")

    assert captured["client_keys"] == ["~/.ssh/db1"]
    assert captured["passphrase"] == "k"


async def test_aclose_closes_cached_connections(monkeypatch):
    conn = FakeConn()

    async def fake_connect(**kwargs):
        return conn

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())
    await pool.run(make_server(), "x")
    await pool.aclose()

    assert conn.closed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ssh_pool.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.ssh')

- [ ] **Step 3: Write implementation**

`src/bot/ssh/__init__.py`: empty file.

`src/bot/ssh/pool.py`:

```python
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

import asyncssh

from bot.config import ServerConfig, SshDefaults


class ServerUnavailable(Exception):
    pass


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_status: int
    duration: float


class SshPool:
    def __init__(self, defaults: SshDefaults) -> None:
        self._defaults = defaults
        self._connections: dict[str, asyncssh.SSHClientConnection] = {}

    async def _connect(self, server: ServerConfig):
        kwargs = {
            "host": server.host,
            "port": server.port,
            "username": server.user,
            "known_hosts": None,
            "connect_timeout": self._defaults.connect_timeout,
        }
        if server.auth.type == "password":
            kwargs["password"] = server.auth.password
        else:
            kwargs["client_keys"] = [os.path.expanduser(server.auth.key_path or "")]
            if server.auth.passphrase:
                kwargs["passphrase"] = server.auth.passphrase
        return await asyncssh.connect(**kwargs)

    async def _get_connection(self, server: ServerConfig):
        connection = self._connections.get(server.id)
        if connection is not None:
            return connection
        connection = await self._connect(server)
        self._connections[server.id] = connection
        return connection

    async def run(
        self, server: ServerConfig, command: str, timeout: float | None = None
    ) -> CommandResult:
        limit = timeout if timeout is not None else self._defaults.command_timeout
        started = time.monotonic()
        try:
            connection = await self._get_connection(server)
            result = await asyncio.wait_for(connection.run(command, check=False), limit)
        except (asyncssh.Error, OSError, asyncio.TimeoutError) as exc:
            self._connections.pop(server.id, None)
            raise ServerUnavailable(str(exc)) from exc
        duration = time.monotonic() - started
        return CommandResult(
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            exit_status=result.exit_status or 0,
            duration=duration,
        )

    async def aclose(self) -> None:
        connections = list(self._connections.values())
        self._connections.clear()
        for connection in connections:
            connection.close()
            await connection.wait_closed()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ssh_pool.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/bot/ssh/__init__.py src/bot/ssh/pool.py tests/test_ssh_pool.py
git commit -m "feat: add asyncssh connection pool"
```

---

### Task 4: System metrics collector

**Files:**
- Create: `src/bot/collectors/__init__.py`
- Create: `src/bot/collectors/system.py`
- Create: `tests/fixtures/system_output.txt`
- Test: `tests/test_collectors_system.py`

**Interfaces:**
- Consumes: `SshPool` (Task 3), `ServerConfig`.
- Produces:
  - `CollectorError(Exception)`
  - `SystemMetrics` dataclass with fields `hostname`, `cpu_percent`, `ram_percent`, `disk_percent`, `load1`, `load5`, `load15`, `cpu_count`, `uptime_seconds` and property `load_per_cpu`
  - `SYSTEM_COMMAND: str`
  - `parse_system_output(text: str) -> SystemMetrics`
  - `async collect_system(pool: SshPool, server: ServerConfig) -> SystemMetrics`

- [ ] **Step 1: Write the fixture**

`tests/fixtures/system_output.txt` (exact content, real tabs only in later fixtures):

```
###HOST
vps-web1
###LOAD
0.15 0.20 0.25 1/234 5678
###NPROC
4
###UPTIME
123456.78 987654.32
###MEM
MemTotal:        2048000 kB
MemFree:          500000 kB
MemAvailable:    1024000 kB
Buffers:           20000 kB
Cached:           300000 kB
###DF
Filesystem     1024-blocks    Used Available Capacity Mounted on
/dev/vda1        8240832 4120416   3700000      53% /
###TOP
top - 10:00:00 up 1 day,  1:00,  1 user,  load average: 0.15, 0.20, 0.25
Tasks: 123 total,   1 running, 122 sleeping,   0 stopped,   0 zombie
%Cpu(s):  5.0 us,  2.0 sy,  0.0 ni, 92.5 id,  0.5 wa,  0.0 hi,  0.0 si,  0.0 st
MiB Mem :   2000.0 total,    488.3 free,    900.0 used,    611.7 buff/cache
MiB Swap:      0.0 total,      0.0 free,      0.0 used.   1000.0 avail Mem
```

- [ ] **Step 2: Write the failing test**

`tests/test_collectors_system.py`:

```python
from pathlib import Path

import pytest

from bot.collectors.system import (
    CollectorError,
    SYSTEM_COMMAND,
    collect_system,
    parse_system_output,
)
from bot.config import ServerConfig
from bot.ssh.pool import CommandResult

FIXTURE = Path(__file__).parent / "fixtures" / "system_output.txt"


def parse_fixture():
    return parse_system_output(FIXTURE.read_text(encoding="utf-8"))


def test_parses_hostname():
    assert parse_fixture().hostname == "vps-web1"


def test_parses_cpu_percent():
    assert parse_fixture().cpu_percent == 7.5


def test_parses_ram_percent():
    assert parse_fixture().ram_percent == 50.0


def test_parses_disk_percent():
    assert parse_fixture().disk_percent == 53.0


def test_parses_load_and_cores():
    metrics = parse_fixture()
    assert (metrics.load1, metrics.load5, metrics.load15) == (0.15, 0.20, 0.25)
    assert metrics.cpu_count == 4
    assert metrics.load_per_cpu == pytest.approx(0.0375)


def test_parses_uptime():
    assert parse_fixture().uptime_seconds == 123456.78


def test_missing_section_raises():
    with pytest.raises(CollectorError):
        parse_system_output("###HOST\nonly\n")


def make_server() -> ServerConfig:
    return ServerConfig(
        id="web1",
        name="Web 1",
        host="1.2.3.4",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


class FakePool:
    def __init__(self, result: CommandResult):
        self._result = result
        self.commands: list[str] = []

    async def run(self, server, command, timeout=None):
        self.commands.append(command)
        return self._result


async def test_collect_system_runs_expected_command():
    pool = FakePool(CommandResult(FIXTURE.read_text(encoding="utf-8"), "", 0, 0.1))
    metrics = await collect_system(pool, make_server())

    assert pool.commands == [SYSTEM_COMMAND]
    assert metrics.hostname == "vps-web1"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_collectors_system.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.collectors')

- [ ] **Step 4: Write implementation**

`src/bot/collectors/__init__.py`: empty file.

`src/bot/collectors/system.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass

from bot.config import ServerConfig
from bot.ssh.pool import SshPool


class CollectorError(Exception):
    pass


@dataclass
class SystemMetrics:
    hostname: str
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    load1: float
    load5: float
    load15: float
    cpu_count: int
    uptime_seconds: float

    @property
    def load_per_cpu(self) -> float:
        if self.cpu_count <= 0:
            return 0.0
        return self.load1 / self.cpu_count


SYSTEM_COMMAND = (
    "echo '###HOST'; hostname; "
    "echo '###LOAD'; cat /proc/loadavg; "
    "echo '###NPROC'; nproc; "
    "echo '###UPTIME'; cat /proc/uptime; "
    "echo '###MEM'; cat /proc/meminfo; "
    "echo '###DF'; df -P /; "
    "echo '###TOP'; top -bn1 2>/dev/null | head -n 5"
)

_SECTION_RE = re.compile(r"^###([A-Z]+)$")
_CPU_IDLE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*id")


def _split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = _SECTION_RE.match(line.strip())
        if match:
            current = match.group(1)
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _require(sections: dict[str, str], name: str) -> str:
    value = sections.get(name)
    if not value:
        raise CollectorError(f"Missing section {name} in system output")
    return value


def parse_cpu_percent(top_section: str) -> float:
    for line in top_section.splitlines():
        if "Cpu(s)" in line or line.startswith("%Cpu"):
            match = _CPU_IDLE_RE.search(line)
            if match:
                return round(100.0 - float(match.group(1)), 1)
    raise CollectorError("Cannot parse CPU usage")


def parse_meminfo(mem_section: str) -> float:
    values: dict[str, float] = {}
    for line in mem_section.splitlines():
        parts = line.split(":")
        if len(parts) != 2:
            continue
        key = parts[0].strip()
        number = parts[1].strip().split()
        if number:
            values[key] = float(number[0])
    if "MemTotal" not in values or "MemAvailable" not in values:
        raise CollectorError("Cannot parse MemTotal/MemAvailable")
    total = values["MemTotal"]
    if total <= 0:
        raise CollectorError("MemTotal is zero")
    return round((total - values["MemAvailable"]) / total * 100.0, 1)


def parse_df(df_section: str) -> float:
    for line in df_section.splitlines()[1:]:
        columns = line.split()
        if len(columns) >= 5 and columns[4].endswith("%"):
            return float(columns[4].rstrip("%"))
    raise CollectorError("Cannot parse df output")


def parse_loadavg(load_section: str) -> tuple[float, float, float]:
    columns = load_section.split()
    if len(columns) < 3:
        raise CollectorError("Cannot parse /proc/loadavg")
    return float(columns[0]), float(columns[1]), float(columns[2])


def parse_uptime(uptime_section: str) -> float:
    columns = uptime_section.split()
    if not columns:
        raise CollectorError("Cannot parse /proc/uptime")
    return float(columns[0])


def parse_system_output(text: str) -> SystemMetrics:
    sections = _split_sections(text)
    load1, load5, load15 = parse_loadavg(_require(sections, "LOAD"))
    cpu_count = int(_require(sections, "NPROC").split()[0])
    return SystemMetrics(
        hostname=_require(sections, "HOST").splitlines()[0].strip(),
        cpu_percent=parse_cpu_percent(_require(sections, "TOP")),
        ram_percent=parse_meminfo(_require(sections, "MEM")),
        disk_percent=parse_df(_require(sections, "DF")),
        load1=load1,
        load5=load5,
        load15=load15,
        cpu_count=cpu_count,
        uptime_seconds=parse_uptime(_require(sections, "UPTIME")),
    )


async def collect_system(pool: SshPool, server: ServerConfig) -> SystemMetrics:
    result = await pool.run(server, SYSTEM_COMMAND)
    if result.exit_status != 0 and not result.stdout:
        raise CollectorError(result.stderr or "system metrics command failed")
    return parse_system_output(result.stdout)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_collectors_system.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/bot/collectors/__init__.py src/bot/collectors/system.py tests/fixtures/system_output.txt tests/test_collectors_system.py
git commit -m "feat: add system metrics collector"
```

---

### Task 5: Docker collector

**Files:**
- Create: `src/bot/collectors/docker.py`
- Create: `tests/fixtures/docker_ps.txt`
- Test: `tests/test_collectors_docker.py`

**Interfaces:**
- Consumes: `SshPool`, `ServerConfig`, `CollectorError`.
- Produces:
  - `ContainerInfo` dataclass: `id: str`, `name: str`, `image: str`, `status: str`
  - `DOCKER_PS_COMMAND: str`
  - `parse_docker_ps(text: str) -> list[ContainerInfo]`
  - `async collect_docker(pool: SshPool, server: ServerConfig) -> list[ContainerInfo]`

- [ ] **Step 1: Write the fixture**

`tests/fixtures/docker_ps.txt` — fields separated by real TAB characters (paste actual tabs, not `\t`):

```
c1a2b3d4e5f6<TAB>web-nginx<TAB>nginx:1.27<TAB>Up 3 days
9f8e7d6c5b4a<TAB>postgres<TAB>db-postgres:16<TAB>Exited (0) 2 hours ago
```

- [ ] **Step 2: Write the failing test**

`tests/test_collectors_docker.py`:

```python
from pathlib import Path

import pytest

from bot.collectors.docker import (
    DOCKER_PS_COMMAND,
    collect_docker,
    parse_docker_ps,
)
from bot.config import ServerConfig
from bot.ssh.pool import CommandResult

FIXTURE = Path(__file__).parent / "fixtures" / "docker_ps.txt"


def test_parse_docker_ps_returns_containers():
    containers = parse_docker_ps(FIXTURE.read_text(encoding="utf-8"))

    assert len(containers) == 2
    assert containers[0].name == "web-nginx"
    assert containers[0].image == "nginx:1.27"
    assert containers[1].status == "Exited (0) 2 hours ago"


def test_parse_docker_ps_ignores_blank_lines():
    assert parse_docker_ps("\n\n") == []


def make_server() -> ServerConfig:
    return ServerConfig(
        id="web1",
        name="Web 1",
        host="1.2.3.4",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


class FakePool:
    def __init__(self, result: CommandResult):
        self._result = result
        self.commands: list[str] = []

    async def run(self, server, command, timeout=None):
        self.commands.append(command)
        return self._result


async def test_collect_docker_runs_expected_command():
    text = FIXTURE.read_text(encoding="utf-8")
    pool = FakePool(CommandResult(text, "", 0, 0.1))
    containers = await collect_docker(pool, make_server())

    assert pool.commands == [DOCKER_PS_COMMAND]
    assert len(containers) == 2
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_collectors_docker.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.collectors.docker')

- [ ] **Step 4: Write implementation**

`src/bot/collectors/docker.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from bot.collectors.system import CollectorError
from bot.config import ServerConfig
from bot.ssh.pool import SshPool


@dataclass
class ContainerInfo:
    id: str
    name: str
    image: str
    status: str


DOCKER_PS_COMMAND = (
    "docker ps -a --format '{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}'"
)


def parse_docker_ps(text: str) -> list[ContainerInfo]:
    containers: list[ContainerInfo] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        columns = line.split("\t")
        if len(columns) < 4:
            continue
        containers.append(
            ContainerInfo(
                id=columns[0].strip(),
                name=columns[1].strip(),
                image=columns[2].strip(),
                status=columns[3].strip(),
            )
        )
    return containers


async def collect_docker(pool: SshPool, server: ServerConfig) -> list[ContainerInfo]:
    result = await pool.run(server, DOCKER_PS_COMMAND)
    if result.exit_status != 0 and not result.stdout:
        raise CollectorError(result.stderr or "docker ps failed")
    return parse_docker_ps(result.stdout)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_collectors_docker.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/bot/collectors/docker.py tests/fixtures/docker_ps.txt tests/test_collectors_docker.py
git commit -m "feat: add docker collector"
```

---

### Task 6: Action builders

**Files:**
- Create: `src/bot/actions/__init__.py`
- Create: `src/bot/actions/base.py`
- Create: `src/bot/actions/services.py`
- Create: `src/bot/actions/updates.py`
- Create: `src/bot/actions/docker.py`
- Create: `src/bot/actions/shell.py`
- Create: `tests/fixtures/systemctl_units.txt`
- Create: `tests/fixtures/apt_upgradable.txt`
- Test: `tests/test_actions.py`

**Interfaces:**
- Consumes: `ServerConfig`.
- Produces:
  - `PreparedAction` frozen dataclass: `server_id`, `title`, `command`, `dangerous`
  - `InvalidArgument(Exception)`
  - `validate_token(value: str, field: str = "argument") -> str`
  - `actions.services`: `LIST_UNITS_COMMAND`, `UnitInfo`, `validate_unit`, `service_action(server, unit, verb) -> PreparedAction`, `parse_systemctl_units(text) -> list[UnitInfo]`, `logs_command(unit, lines=50) -> str`
  - `actions.updates`: `UPGRADABLE_COMMAND`, `UPGRADE_COMMAND`, `REBOOT_COMMAND`, `parse_upgradable(text) -> list[str]`, `upgrade_action(server) -> PreparedAction`, `reboot_action(server) -> PreparedAction`
  - `actions.docker`: `validate_container`, `docker_restart_action(server, name)`, `docker_logs_command(name, lines=50)`
  - `actions.shell`: `shell_action(server, command) -> PreparedAction`

- [ ] **Step 1: Write the fixtures**

`tests/fixtures/systemctl_units.txt` (single spaces; parsed by whitespace split):

```
nginx.service    loaded active running A high performance web server
ssh.service      loaded active running OpenBSD Secure Shell server
cron.service     loaded active running Regular background program processing daemon
```

`tests/fixtures/apt_upgradable.txt`:

```
Listing...
nginx/jammy-updates 1.18.0-0ubuntu1.4 amd64 [upgradable from: 1.18.0-0ubuntu1.3]
openssl/jammy-security 3.0.2-0ubuntu1.12 amd64 [upgradable from: 3.0.2-0ubuntu1.10]
```

- [ ] **Step 2: Write the failing test**

`tests/test_actions.py`:

```python
from pathlib import Path

import pytest

from bot.actions import docker as docker_actions
from bot.actions import services, updates
from bot.actions.base import InvalidArgument, PreparedAction, validate_token
from bot.actions.shell import shell_action
from bot.config import ServerConfig

FIXTURES = Path(__file__).parent / "fixtures"


def make_server() -> ServerConfig:
    return ServerConfig(
        id="web1",
        name="Web 1",
        host="1.2.3.4",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


def test_validate_token_accepts_safe_values():
    assert validate_token("nginx.service", "unit") == "nginx.service"
    assert validate_token("my-container_1") == "my-container_1"


def test_validate_token_rejects_shell_metacharacters():
    for bad in ["a; rm -rf /", "a && b", "a|b", "a$(whoami)", "a b"]:
        with pytest.raises(InvalidArgument):
            validate_token(bad)


def test_service_action_is_dangerous():
    action = services.service_action(make_server(), "nginx", "restart")

    assert isinstance(action, PreparedAction)
    assert action.dangerous is True
    assert action.command == "systemctl restart nginx"
    assert action.server_id == "web1"


def test_service_action_rejects_bad_unit():
    with pytest.raises(InvalidArgument):
        services.service_action(make_server(), "nginx; reboot", "restart")


def test_parse_systemctl_units():
    units = services.parse_systemctl_units(
        (FIXTURES / "systemctl_units.txt").read_text(encoding="utf-8")
    )

    assert [u.name for u in units] == ["nginx.service", "ssh.service", "cron.service"]
    assert units[0].active == "active"


def test_logs_command():
    assert services.logs_command("nginx", 20) == "journalctl -u nginx -n 20 --no-pager"


def test_parse_upgradable():
    packages = updates.parse_upgradable(
        (FIXTURES / "apt_upgradable.txt").read_text(encoding="utf-8")
    )

    assert packages == ["nginx", "openssl"]


def test_upgrade_action_is_dangerous():
    action = updates.upgrade_action(make_server())

    assert action.dangerous is True
    assert action.command == updates.UPGRADE_COMMAND


def test_reboot_action_is_dangerous():
    action = updates.reboot_action(make_server())

    assert action.dangerous is True
    assert action.command == updates.REBOOT_COMMAND


def test_docker_restart_action():
    action = docker_actions.docker_restart_action(make_server(), "web-nginx")

    assert action.command == "docker restart web-nginx"
    assert action.dangerous is True


def test_docker_restart_rejects_bad_name():
    with pytest.raises(InvalidArgument):
        docker_actions.docker_restart_action(make_server(), "web; reboot")


def test_docker_logs_command():
    assert (
        docker_actions.docker_logs_command("web-nginx", 30)
        == "docker logs --tail 30 web-nginx"
    )


def test_shell_action_is_dangerous_and_keeps_command():
    action = shell_action(make_server(), "df -h && uptime")

    assert action.dangerous is True
    assert action.command == "df -h && uptime"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_actions.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.actions')

- [ ] **Step 4: Write implementation**

`src/bot/actions/__init__.py`: empty file.

`src/bot/actions/base.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"^[A-Za-z0-9@_.:/-]+$")


class InvalidArgument(Exception):
    pass


@dataclass(frozen=True)
class PreparedAction:
    server_id: str
    title: str
    command: str
    dangerous: bool


def validate_token(value: str, field: str = "argument") -> str:
    if not value or not _TOKEN_RE.match(value):
        raise InvalidArgument(f"Invalid {field}: {value!r}")
    return value
```

`src/bot/actions/services.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass

from bot.actions.base import InvalidArgument, PreparedAction, validate_token
from bot.config import ServerConfig

_UNIT_RE = re.compile(r"^[A-Za-z0-9@_.-]+$")

LIST_UNITS_COMMAND = (
    "systemctl list-units --type=service --state=running --no-pager --plain"
)


@dataclass
class UnitInfo:
    name: str
    load: str
    active: str
    sub: str


def validate_unit(name: str) -> str:
    if not name or not _UNIT_RE.match(name):
        raise InvalidArgument(f"Invalid unit: {name!r}")
    return name


def service_action(server: ServerConfig, unit: str, verb: str) -> PreparedAction:
    if verb not in {"start", "stop", "restart"}:
        raise InvalidArgument(f"Invalid verb: {verb!r}")
    safe_unit = validate_unit(unit)
    return PreparedAction(
        server_id=server.id,
        title=f"{verb} {safe_unit}",
        command=f"systemctl {verb} {safe_unit}",
        dangerous=verb in {"stop", "restart"},
    )


def parse_systemctl_units(text: str) -> list[UnitInfo]:
    units: list[UnitInfo] = []
    for line in text.splitlines():
        columns = line.split()
        if len(columns) < 4:
            continue
        if not columns[0].endswith(".service"):
            continue
        units.append(
            UnitInfo(
                name=columns[0],
                load=columns[1],
                active=columns[2],
                sub=columns[3],
            )
        )
    return units


def logs_command(unit: str, lines: int = 50) -> str:
    safe_unit = validate_unit(unit)
    return f"journalctl -u {safe_unit} -n {int(lines)} --no-pager"
```

`src/bot/actions/updates.py`:

```python
from __future__ import annotations

from bot.actions.base import PreparedAction
from bot.config import ServerConfig

UPGRADABLE_COMMAND = "apt list --upgradable 2>/dev/null"
UPGRADE_COMMAND = "DEBIAN_FRONTEND=noninteractive apt-get -y upgrade"
REBOOT_COMMAND = "systemctl reboot"


def parse_upgradable(text: str) -> list[str]:
    packages: list[str] = []
    for line in text.splitlines():
        if "/" not in line:
            continue
        name = line.split("/", 1)[0].strip()
        if name and " " not in name:
            packages.append(name)
    return packages


def upgrade_action(server: ServerConfig) -> PreparedAction:
    return PreparedAction(
        server_id=server.id,
        title="apt upgrade",
        command=UPGRADE_COMMAND,
        dangerous=True,
    )


def reboot_action(server: ServerConfig) -> PreparedAction:
    return PreparedAction(
        server_id=server.id,
        title="reboot",
        command=REBOOT_COMMAND,
        dangerous=True,
    )
```

`src/bot/actions/docker.py`:

```python
from __future__ import annotations

from bot.actions.base import PreparedAction, validate_token
from bot.config import ServerConfig


def validate_container(name: str) -> str:
    return validate_token(name, "container")


def docker_restart_action(server: ServerConfig, name: str) -> PreparedAction:
    safe_name = validate_container(name)
    return PreparedAction(
        server_id=server.id,
        title=f"docker restart {safe_name}",
        command=f"docker restart {safe_name}",
        dangerous=True,
    )


def docker_logs_command(name: str, lines: int = 50) -> str:
    safe_name = validate_container(name)
    return f"docker logs --tail {int(lines)} {safe_name}"
```

`src/bot/actions/shell.py`:

```python
from __future__ import annotations

from bot.actions.base import PreparedAction
from bot.config import ServerConfig


def shell_action(server: ServerConfig, command: str) -> PreparedAction:
    return PreparedAction(
        server_id=server.id,
        title="shell",
        command=command,
        dangerous=True,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_actions.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/bot/actions tests/fixtures/systemctl_units.txt tests/fixtures/apt_upgradable.txt tests/test_actions.py
git commit -m "feat: add action builders with argument validation"
```

---

### Task 7: Security (whitelist and confirmations)

**Files:**
- Create: `src/bot/security.py`
- Test: `tests/test_security.py`

**Interfaces:**
- Consumes: `PreparedAction` from `bot.actions.base`.
- Produces:
  - `PendingAction` dataclass: `user_id: int`, `action: PreparedAction`, `expires_at: float`
  - `ConfirmationStore(ttl: float = 60.0, clock=time.monotonic)` with `create(user_id, action) -> str` and `take(user_id, token) -> PreparedAction | None`
  - `WhitelistMiddleware(allowed_users: Iterable[int])` (aiogram `BaseMiddleware`, reads `data["event_from_user"]`)

- [ ] **Step 1: Write the failing test**

`tests/test_security.py`:

```python
from bot.actions.base import PreparedAction
from bot.security import ConfirmationStore, WhitelistMiddleware


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


ACTION = PreparedAction("web1", "restart nginx", "systemctl restart nginx", True)


def test_confirmation_roundtrip():
    store = ConfirmationStore(clock=FakeClock())
    token = store.create(1, ACTION)

    assert store.take(1, token) is ACTION


def test_confirmation_is_single_use():
    store = ConfirmationStore(clock=FakeClock())
    token = store.create(1, ACTION)
    store.take(1, token)

    assert store.take(1, token) is None


def test_confirmation_rejects_wrong_user():
    store = ConfirmationStore(clock=FakeClock())
    token = store.create(1, ACTION)

    assert store.take(2, token) is None


def test_confirmation_expires():
    clock = FakeClock()
    store = ConfirmationStore(ttl=60.0, clock=clock)
    token = store.create(1, ACTION)
    clock.now = 61.0

    assert store.take(1, token) is None


def test_confirmation_unknown_token():
    store = ConfirmationStore(clock=FakeClock())

    assert store.take(1, "nope") is None


async def test_whitelist_blocks_unknown_user():
    middleware = WhitelistMiddleware([1])
    called = False

    async def handler(event, data):
        nonlocal called
        called = True
        return "ok"

    result = await middleware(handler, None, {"event_from_user": FakeUser(2)})

    assert result is None
    assert called is False


async def test_whitelist_allows_known_user():
    middleware = WhitelistMiddleware([1])

    async def handler(event, data):
        return "ok"

    result = await middleware(handler, None, {"event_from_user": FakeUser(1)})

    assert result == "ok"


async def test_whitelist_blocks_missing_user():
    middleware = WhitelistMiddleware([1])

    async def handler(event, data):
        return "ok"

    assert await middleware(handler, None, {}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_security.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.security')

- [ ] **Step 3: Write implementation**

`src/bot/security.py`:

```python
from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass
from typing import Iterable

from aiogram import BaseMiddleware

from bot.actions.base import PreparedAction

logger = logging.getLogger(__name__)


@dataclass
class PendingAction:
    user_id: int
    action: PreparedAction
    expires_at: float


class ConfirmationStore:
    def __init__(self, ttl: float = 60.0, clock=time.monotonic) -> None:
        self._ttl = ttl
        self._clock = clock
        self._pending: dict[str, PendingAction] = {}

    def create(self, user_id: int, action: PreparedAction) -> str:
        token = secrets.token_hex(4)
        self._pending[token] = PendingAction(
            user_id=user_id,
            action=action,
            expires_at=self._clock() + self._ttl,
        )
        return token

    def take(self, user_id: int, token: str) -> PreparedAction | None:
        item = self._pending.pop(token, None)
        if item is None:
            return None
        if item.user_id != user_id:
            return None
        if item.expires_at < self._clock():
            return None
        return item.action


class WhitelistMiddleware(BaseMiddleware):
    def __init__(self, allowed_users: Iterable[int]) -> None:
        self._allowed = set(allowed_users)

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None or user.id not in self._allowed:
            logger.warning("Blocked access attempt from user %s", getattr(user, "id", None))
            return None
        return await handler(event, data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_security.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/security.py tests/test_security.py
git commit -m "feat: add whitelist middleware and confirmation store"
```

---

### Task 8: Alert engine

**Files:**
- Create: `src/bot/alerts/__init__.py`
- Create: `src/bot/alerts/engine.py`
- Test: `tests/test_alerts.py`

**Interfaces:**
- Consumes: `Thresholds` from `bot.config`, `SystemMetrics` from `bot.collectors.system`.
- Produces:
  - `AlertEvent` frozen dataclass: `server_id: str`, `problem: str`, `kind: str`, `detail: str`
  - `AlertRuntime` dataclass: `enabled: bool = True`
  - `AlertEngine(thresholds: Thresholds, cooldown: float, clock=time.monotonic)` with `evaluate(server_id, metrics) -> list[AlertEvent]`, `evaluate_offline(server_id) -> list[AlertEvent]`, `mark_online(server_id) -> list[AlertEvent]`

- [ ] **Step 1: Write the failing test**

`tests/test_alerts.py`:

```python
from bot.alerts.engine import AlertEngine
from bot.collectors.system import SystemMetrics
from bot.config import Thresholds


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def metrics(cpu=10.0, ram=10.0, disk=10.0, load=0.1, cores=2) -> SystemMetrics:
    return SystemMetrics("h", cpu, ram, disk, load, load, load, cores, 1.0)


def make_engine(clock=None, cooldown=300.0) -> AlertEngine:
    return AlertEngine(
        Thresholds(cpu_percent=85, ram_percent=90, disk_percent=85, load_per_cpu=2.0),
        cooldown,
        clock or FakeClock(),
    )


def test_healthy_metrics_emit_nothing():
    assert make_engine().evaluate("web1", metrics()) == []


def test_cpu_breach_emits_enter():
    events = make_engine().evaluate("web1", metrics(cpu=95))

    assert len(events) == 1
    assert events[0].problem == "cpu"
    assert events[0].kind == "enter"


def test_persisting_breach_does_not_repeat():
    engine = make_engine()
    engine.evaluate("web1", metrics(cpu=95))

    assert engine.evaluate("web1", metrics(cpu=96)) == []


def test_recovery_emits_resolve():
    engine = make_engine()
    engine.evaluate("web1", metrics(cpu=95))
    events = engine.evaluate("web1", metrics(cpu=10))

    assert len(events) == 1
    assert events[0].problem == "cpu"
    assert events[0].kind == "resolve"


def test_ram_and_disk_and_load_breaches():
    events = make_engine().evaluate(
        "web1", metrics(cpu=10, ram=95, disk=90, load=5.0, cores=2)
    )

    assert sorted(e.problem for e in events) == ["disk", "load", "ram"]


def test_cooldown_suppresses_reentry_then_allows():
    clock = FakeClock()
    engine = make_engine(clock=clock, cooldown=300)
    engine.evaluate("web1", metrics(cpu=95))
    clock.now = 10
    engine.evaluate("web1", metrics(cpu=10))
    clock.now = 20
    assert engine.evaluate("web1", metrics(cpu=95)) == []
    clock.now = 310
    events = engine.evaluate("web1", metrics(cpu=95))
    assert [e.kind for e in events] == ["enter"]


def test_offline_enter_and_resolve():
    engine = make_engine()
    offline = engine.evaluate_offline("web1")
    assert [e.problem for e in offline] == ["offline"]
    assert offline[0].kind == "enter"

    resolved = engine.mark_online("web1")
    assert [e.problem for e in resolved] == ["offline"]
    assert resolved[0].kind == "resolve"


def test_offline_disabled_returns_empty():
    engine = AlertEngine(
        Thresholds(offline=False), 300.0, FakeClock()
    )

    assert engine.evaluate_offline("web1") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alerts.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.alerts')

- [ ] **Step 3: Write implementation**

`src/bot/alerts/__init__.py`: empty file.

`src/bot/alerts/engine.py`:

```python
from __future__ import annotations

import time
from dataclasses import dataclass

from bot.collectors.system import SystemMetrics
from bot.config import Thresholds


@dataclass(frozen=True)
class AlertEvent:
    server_id: str
    problem: str
    kind: str
    detail: str


@dataclass
class AlertRuntime:
    enabled: bool = True


class AlertEngine:
    def __init__(
        self, thresholds: Thresholds, cooldown: float, clock=time.monotonic
    ) -> None:
        self._thresholds = thresholds
        self._cooldown = cooldown
        self._clock = clock
        self._active: dict[str, set[str]] = {}
        self._last_sent: dict[tuple[str, str], float] = {}

    def _transition(
        self, server_id: str, problems: dict[str, str], now: float
    ) -> list[AlertEvent]:
        previous = self._active.get(server_id, set())
        current = set(problems)
        new_active = set(previous)
        events: list[AlertEvent] = []

        for name in sorted(current - previous):
            key = (server_id, name)
            last = self._last_sent.get(key)
            if last is None or now - last >= self._cooldown:
                self._last_sent[key] = now
                new_active.add(name)
                events.append(AlertEvent(server_id, name, "enter", problems[name]))

        for name in sorted(previous - current):
            new_active.discard(name)
            events.append(AlertEvent(server_id, name, "resolve", ""))

        self._active[server_id] = new_active
        return events

    def evaluate(self, server_id: str, metrics: SystemMetrics) -> list[AlertEvent]:
        problems: dict[str, str] = {}
        if metrics.cpu_percent > self._thresholds.cpu_percent:
            problems["cpu"] = f"CPU {metrics.cpu_percent:.0f}%"
        if metrics.ram_percent > self._thresholds.ram_percent:
            problems["ram"] = f"RAM {metrics.ram_percent:.0f}%"
        if metrics.disk_percent > self._thresholds.disk_percent:
            problems["disk"] = f"диск {metrics.disk_percent:.0f}%"
        if metrics.load_per_cpu > self._thresholds.load_per_cpu:
            problems["load"] = f"load {metrics.load_per_cpu:.2f}/CPU"
        return self._transition(server_id, problems, self._clock())

    def evaluate_offline(self, server_id: str) -> list[AlertEvent]:
        if not self._thresholds.offline:
            return []
        return self._transition(
            server_id, {"offline": "сервер недоступен"}, self._clock()
        )

    def mark_online(self, server_id: str) -> list[AlertEvent]:
        return self._transition(server_id, {}, self._clock())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alerts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/alerts/__init__.py src/bot/alerts/engine.py tests/test_alerts.py
git commit -m "feat: add in-memory alert engine"
```

---

### Task 9: Formatting

**Files:**
- Create: `src/bot/formatting.py`
- Test: `tests/test_formatting.py`

**Interfaces:**
- Consumes: `ServerConfig`, `SystemMetrics`, `AlertEvent`, `CommandResult`.
- Produces:
  - `truncate_output(text: str, max_lines: int) -> str`
  - `format_duration(seconds: float) -> str`
  - `format_metrics(server: ServerConfig, metrics: SystemMetrics) -> str`
  - `format_alert(event: AlertEvent, server: ServerConfig) -> str`
  - `format_command_result(result: CommandResult, max_lines: int) -> str`

- [ ] **Step 1: Write the failing test**

`tests/test_formatting.py`:

```python
from bot.alerts.engine import AlertEvent
from bot.collectors.system import SystemMetrics
from bot.config import ServerConfig
from bot.formatting import (
    format_alert,
    format_command_result,
    format_duration,
    format_metrics,
    truncate_output,
)
from bot.ssh.pool import CommandResult


def make_server() -> ServerConfig:
    return ServerConfig(
        id="web1",
        name="Web 1",
        host="1.2.3.4",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


def make_metrics() -> SystemMetrics:
    return SystemMetrics("vps-web1", 12.5, 40.0, 53.0, 0.5, 0.4, 0.3, 4, 90061.0)


def test_truncate_output_keeps_short_text():
    assert truncate_output("a\nb", 10) == "a\nb"


def test_truncate_output_cuts_long_text():
    text = "\n".join(str(i) for i in range(50))
    result = truncate_output(text, 10)

    assert result.startswith("0\n1\n")
    assert "усечено" in result


def test_format_duration():
    assert format_duration(90061) == "1д 1ч 1м"


def test_format_metrics_contains_fields():
    text = format_metrics(make_server(), make_metrics())

    assert "Web 1" in text
    assert "12.5%" in text
    assert "40.0%" in text
    assert "53%" in text
    assert "1д 1ч 1м" in text


def test_format_alert_enter_uses_detail():
    event = AlertEvent("web1", "cpu", "enter", "CPU 95%")
    text = format_alert(event, make_server())

    assert "Web 1" in text
    assert "CPU 95%" in text


def test_format_alert_offline():
    event = AlertEvent("web1", "offline", "enter", "сервер недоступен")
    text = format_alert(event, make_server())

    assert "недоступен" in text


def test_format_alert_resolve():
    event = AlertEvent("web1", "cpu", "resolve", "")
    text = format_alert(event, make_server())

    assert "норм" in text


def test_format_command_result_escapes_and_truncates():
    result = CommandResult("a\nb\nc", "", 0, 0.4)
    text = format_command_result(result, 2)

    assert "a" in text
    assert "код: 0" in text
    assert "усечено" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_formatting.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.formatting')

- [ ] **Step 3: Write implementation**

`src/bot/formatting.py`:

```python
from __future__ import annotations

import html

from bot.alerts.engine import AlertEvent
from bot.collectors.system import SystemMetrics
from bot.config import ServerConfig
from bot.ssh.pool import CommandResult


def truncate_output(text: str, max_lines: int) -> str:
    lines = text.rstrip("\n").splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    shown = lines[:max_lines]
    return "\n".join(shown) + f"\n… усечено ({len(lines) - max_lines} строк)"


def format_duration(seconds: float) -> str:
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    parts.append(f"{minutes}м")
    return " ".join(parts)


def format_metrics(server: ServerConfig, metrics: SystemMetrics) -> str:
    return (
        f"📊 <b>{server.name}</b> ({server.host})\n"
        f"hostname: {metrics.hostname}\n"
        f"CPU: {metrics.cpu_percent:.1f}% (ядер: {metrics.cpu_count})\n"
        f"RAM: {metrics.ram_percent:.1f}%\n"
        f"Диск /: {metrics.disk_percent:.0f}%\n"
        f"Load: {metrics.load1:.2f} {metrics.load5:.2f} {metrics.load15:.2f}\n"
        f"Uptime: {format_duration(metrics.uptime_seconds)}"
    )


def format_alert(event: AlertEvent, server: ServerConfig) -> str:
    if event.kind == "resolve":
        return f"🟢 <b>{server.name}</b>: {event.problem} в норме"
    if event.problem == "offline":
        return f"🔴 <b>{server.name}</b>: сервер недоступен"
    return f"🟠 <b>{server.name}</b>: {event.detail}"


def format_command_result(result: CommandResult, max_lines: int) -> str:
    body = result.stdout or result.stderr or "(пустой вывод)"
    escaped = html.escape(body)
    return (
        truncate_output(escaped, max_lines)
        + f"\n\nкод: {result.exit_status}, {result.duration:.1f}с"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_formatting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/formatting.py tests/test_formatting.py
git commit -m "feat: add message formatting helpers"
```

---

### Task 10: Keyboards

**Files:**
- Create: `src/bot/keyboards.py`
- Test: `tests/test_keyboards.py`

**Interfaces:**
- Consumes: `ServerConfig`.
- Produces:
  - `servers_keyboard(servers: Sequence[ServerConfig]) -> InlineKeyboardMarkup`
  - `server_menu_keyboard(server_id: str) -> InlineKeyboardMarkup`
  - `units_keyboard(unit_names: Sequence[str]) -> InlineKeyboardMarkup`
  - `unit_actions_keyboard(index: int) -> InlineKeyboardMarkup`
  - `confirm_keyboard(token: str) -> InlineKeyboardMarkup`
  - `docker_keyboard(container_names: Sequence[str]) -> InlineKeyboardMarkup`

- [ ] **Step 1: Write the failing test**

`tests/test_keyboards.py`:

```python
from bot.config import ServerConfig
from bot.keyboards import (
    confirm_keyboard,
    docker_keyboard,
    server_menu_keyboard,
    servers_keyboard,
    unit_actions_keyboard,
    units_keyboard,
)


def make_server() -> ServerConfig:
    return ServerConfig(
        id="web1",
        name="Web 1",
        host="1.2.3.4",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


def callbacks(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_servers_keyboard():
    assert callbacks(servers_keyboard([make_server()])) == ["menu:web1"]


def test_server_menu_keyboard_contains_all_actions():
    data = callbacks(server_menu_keyboard("web1"))

    assert "metrics:web1" in data
    assert "units:web1" in data
    assert "updates:web1" in data
    assert "docker:web1" in data
    assert "shell:web1" in data
    assert "reboot:web1" in data


def test_units_keyboard_indexes_units():
    assert callbacks(units_keyboard(["nginx", "ssh"])) == ["unit:0", "unit:1"]


def test_unit_actions_keyboard():
    data = callbacks(unit_actions_keyboard(2))

    assert data == ["unitact:restart:2", "unitact:stop:2", "unitact:start:2", "unitlogs:2"]


def test_confirm_keyboard():
    data = callbacks(confirm_keyboard("abcd"))

    assert data == ["confirm:abcd", "cancel:abcd"]


def test_docker_keyboard():
    assert callbacks(docker_keyboard(["web"])) == ["dlog:0", "drestart:0"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keyboards.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.keyboards')

- [ ] **Step 3: Write implementation**

`src/bot/keyboards.py`:

```python
from __future__ import annotations

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import ServerConfig


def servers_keyboard(servers: Sequence[ServerConfig]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=server.name, callback_data=f"menu:{server.id}")]
        for server in servers
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def server_menu_keyboard(server_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Метрики", callback_data=f"metrics:{server_id}")],
            [InlineKeyboardButton(text="⚙️ Сервисы", callback_data=f"units:{server_id}")],
            [InlineKeyboardButton(text="📦 Обновления", callback_data=f"updates:{server_id}")],
            [InlineKeyboardButton(text="🐳 Docker", callback_data=f"docker:{server_id}")],
            [InlineKeyboardButton(text="💻 Shell", callback_data=f"shell:{server_id}")],
            [InlineKeyboardButton(text="🔄 Reboot", callback_data=f"reboot:{server_id}")],
        ]
    )


def units_keyboard(unit_names: Sequence[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"unit:{index}")]
        for index, name in enumerate(unit_names)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def unit_actions_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Restart", callback_data=f"unitact:restart:{index}"),
                InlineKeyboardButton(text="⏹ Stop", callback_data=f"unitact:stop:{index}"),
                InlineKeyboardButton(text="▶️ Start", callback_data=f"unitact:start:{index}"),
            ],
            [InlineKeyboardButton(text="📜 Логи", callback_data=f"unitlogs:{index}")],
        ]
    )


def docker_keyboard(container_names: Sequence[str]) -> InlineKeyboardMarkup:
    rows = []
    for index, name in enumerate(container_names):
        rows.append(
            [
                InlineKeyboardButton(text=f"📜 {name}", callback_data=f"dlog:{index}"),
                InlineKeyboardButton(text=f"🔄 {name}", callback_data=f"drestart:{index}"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{token}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel:{token}"),
            ]
        ]
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keyboards.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/keyboards.py tests/test_keyboards.py
git commit -m "feat: add inline keyboards"
```

---

### Task 11: Handler infrastructure, start, servers, status

**Files:**
- Create: `src/bot/handlers/__init__.py`
- Create: `src/bot/handlers/common.py`
- Create: `src/bot/handlers/start.py`
- Create: `src/bot/handlers/servers.py`
- Create: `src/bot/handlers/status.py`
- Test: `tests/test_handlers_common.py`

**Interfaces:**
- Consumes: `AppConfig`, `SshPool`, `ConfirmationStore`, `AlertRuntime`, `parse_callback` helpers.
- Produces:
  - `ShellState` (FSM state `waiting_command`), `MenuState` (FSM states `units`, `docker`)
  - `DependenciesMiddleware(config, pool, confirmations, runtime)` injecting `config`, `pool`, `confirmations`, `runtime` into handler data
  - `parse_callback(data: str) -> tuple[str, str]`
  - `async run_command(pool, server, command, max_lines, answer) -> None`
  - routers: `start.router`, `servers.router`, `status.router`

- [ ] **Step 1: Write the failing test**

`tests/test_handlers_common.py`:

```python
from bot.config import ServerConfig
from bot.handlers.common import parse_callback, run_command
from bot.ssh.pool import CommandResult, ServerUnavailable


def make_server() -> ServerConfig:
    return ServerConfig(
        id="web1",
        name="Web 1",
        host="1.2.3.4",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


class ErrorPool:
    async def run(self, *args, **kwargs):
        raise ServerUnavailable("boom")


class OkPool:
    def __init__(self, result: CommandResult) -> None:
        self._result = result

    async def run(self, *args, **kwargs) -> CommandResult:
        return self._result


def test_parse_callback():
    assert parse_callback("metrics:web1") == ("metrics", "web1")
    assert parse_callback("alerts:toggle") == ("alerts", "toggle")


async def test_run_command_reports_unavailable():
    seen: list[str] = []

    async def answer(text: str) -> None:
        seen.append(text)

    await run_command(ErrorPool(), make_server(), "x", 10, answer)

    assert "недоступен" in seen[0]


async def test_run_command_returns_output():
    seen: list[str] = []

    async def answer(text: str) -> None:
        seen.append(text)

    result = CommandResult("hello", "", 0, 0.2)
    await run_command(OkPool(result), make_server(), "x", 10, answer)

    assert "hello" in seen[0]
    assert "код: 0" in seen[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_handlers_common.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.handlers')

- [ ] **Step 3: Write implementation**

`src/bot/handlers/__init__.py`: empty file.

`src/bot/handlers/common.py`:

```python
from __future__ import annotations

from aiogram import BaseMiddleware
from aiogram.fsm.state import State, StatesGroup

from bot.alerts.engine import AlertRuntime
from bot.config import AppConfig, ServerConfig
from bot.formatting import format_command_result
from bot.security import ConfirmationStore
from bot.ssh.pool import ServerUnavailable, SshPool


class ShellState(StatesGroup):
    waiting_command = State()


class MenuState(StatesGroup):
    units = State()
    docker = State()


class DependenciesMiddleware(BaseMiddleware):
    def __init__(
        self,
        config: AppConfig,
        pool: SshPool,
        confirmations: ConfirmationStore,
        runtime: AlertRuntime,
    ) -> None:
        self._config = config
        self._pool = pool
        self._confirmations = confirmations
        self._runtime = runtime

    async def __call__(self, handler, event, data):
        data["config"] = self._config
        data["pool"] = self._pool
        data["confirmations"] = self._confirmations
        data["runtime"] = self._runtime
        return await handler(event, data)


def parse_callback(data: str) -> tuple[str, str]:
    action, _, value = data.partition(":")
    return action, value


async def run_command(
    pool: SshPool,
    server: ServerConfig,
    command: str,
    max_lines: int,
    answer,
) -> None:
    try:
        result = await pool.run(server, command)
    except ServerUnavailable as exc:
        await answer(f"❌ {server.name}: недоступен ({exc})")
        return
    await answer(format_command_result(result, max_lines))
```

`src/bot/handlers/start.py`:

```python
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

HELP_TEXT = (
    "<b>VPS Manager</b>\n\n"
    "/servers — список серверов\n"
    "/statusall — сводка по всем серверам\n"
    "/status &lt;id&gt; — метрики сервера\n"
    "/shell &lt;id&gt; — выполнить команду\n"
    "/alerts — состояние уведомлений"
)


@router.message(Command("start", "help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")
```

`src/bot/handlers/servers.py`:

```python
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.collectors.system import CollectorError, collect_system
from bot.config import AppConfig
from bot.keyboards import servers_keyboard
from bot.ssh.pool import ServerUnavailable, SshPool

router = Router()


@router.message(Command("servers"))
async def cmd_servers(message: Message, config: AppConfig) -> None:
    await message.answer("Серверы:", reply_markup=servers_keyboard(config.servers))


@router.message(Command("statusall"))
async def cmd_statusall(message: Message, config: AppConfig, pool: SshPool) -> None:
    lines = []
    for server in config.servers:
        try:
            metrics = await collect_system(pool, server)
        except (ServerUnavailable, CollectorError) as exc:
            lines.append(f"🔴 {server.name}: недоступен ({exc})")
            continue
        lines.append(
            f"🟢 {server.name}: CPU {metrics.cpu_percent:.0f}% "
            f"RAM {metrics.ram_percent:.0f}% Диск {metrics.disk_percent:.0f}%"
        )
    await message.answer("\n".join(lines))
```

`src/bot/handlers/status.py`:

```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.collectors.system import CollectorError, collect_system
from bot.config import AppConfig, ServerConfig
from bot.formatting import format_metrics
from bot.ssh.pool import ServerUnavailable, SshPool

router = Router()


async def send_metrics(
    answer, pool: SshPool, server: ServerConfig
) -> None:
    try:
        metrics = await collect_system(pool, server)
    except (ServerUnavailable, CollectorError) as exc:
        await answer(f"❌ {server.name}: недоступен ({exc})")
        return
    await answer(format_metrics(server, metrics), parse_mode="HTML")


@router.message(Command("status"))
async def cmd_status(message: Message, config: AppConfig, pool: SshPool) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /status <server_id>")
        return
    server = config.server(parts[1].strip())
    if server is None:
        await message.answer("Сервер не найден")
        return
    await send_metrics(message.answer, pool, server)


@router.callback_query(F.data.startswith("metrics:"))
async def cb_metrics(callback: CallbackQuery, config: AppConfig, pool: SshPool) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    await send_metrics(callback.message.answer, pool, server)
    await callback.answer()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_handlers_common.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/handlers tests/test_handlers_common.py
git commit -m "feat: add handler infrastructure, start, servers and status"
```

---

### Task 12: Handlers for services, updates, docker, confirmation

**Files:**
- Create: `src/bot/handlers/services.py`
- Create: `src/bot/handlers/updates.py`
- Create: `src/bot/handlers/docker.py`
- Create: `src/bot/handlers/confirm.py`
- Test: `tests/test_handlers_wiring.py`

**Interfaces:**
- Consumes: actions (Task 6), collectors (Task 4-5), keyboards (Task 10), states/`run_command` (Task 11).
- Produces: routers `services.router`, `updates.router`, `docker.router`, `confirm.router`.

- [ ] **Step 1: Write the failing test**

`tests/test_handlers_wiring.py`:

```python
from aiogram import Router

from bot.handlers import confirm, docker, services, updates


def test_new_routers_are_routers():
    for module in (services, updates, docker, confirm):
        assert isinstance(module.router, Router)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_handlers_wiring.py -v`
Expected: FAIL (ImportError: cannot import name 'services')

- [ ] **Step 3: Write implementation**

`src/bot/handlers/services.py`:

```python
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.actions.base import InvalidArgument
from bot.actions.services import (
    LIST_UNITS_COMMAND,
    logs_command,
    parse_systemctl_units,
    service_action,
)
from bot.config import AppConfig
from bot.handlers.common import MenuState, run_command
from bot.keyboards import confirm_keyboard, unit_actions_keyboard, units_keyboard
from bot.security import ConfirmationStore
from bot.ssh.pool import ServerUnavailable, SshPool

router = Router()


@router.callback_query(F.data.startswith("units:"))
async def cb_units(
    callback: CallbackQuery, state: FSMContext, config: AppConfig, pool: SshPool
) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    try:
        result = await pool.run(server, LIST_UNITS_COMMAND)
    except ServerUnavailable as exc:
        await callback.answer(f"Недоступен: {exc}", show_alert=True)
        return
    units = [unit.name for unit in parse_systemctl_units(result.stdout)]
    await state.set_state(MenuState.units)
    await state.update_data(server_id=server_id, units=units)
    await callback.message.answer("Выбери сервис:", reply_markup=units_keyboard(units))
    await callback.answer()


@router.callback_query(F.data.startswith("unit:"), MenuState.units)
async def cb_unit(callback: CallbackQuery, state: FSMContext) -> None:
    index = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    units = data.get("units", [])
    if index >= len(units):
        await callback.answer("Список устарел", show_alert=True)
        return
    await state.update_data(selected=index)
    await callback.message.answer(units[index], reply_markup=unit_actions_keyboard(index))
    await callback.answer()


@router.callback_query(F.data.startswith("unitact:"), MenuState.units)
async def cb_unitact(
    callback: CallbackQuery,
    state: FSMContext,
    config: AppConfig,
    confirmations: ConfirmationStore,
) -> None:
    parts = callback.data.split(":")
    verb, raw_index = parts[1], int(parts[2])
    data = await state.get_data()
    units = data.get("units", [])
    server = config.server(data.get("server_id", ""))
    if server is None or raw_index >= len(units):
        await callback.answer("Список устарел", show_alert=True)
        return
    try:
        action = service_action(server, units[raw_index], verb)
    except InvalidArgument as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    token = confirmations.create(callback.from_user.id, action)
    await callback.message.answer(
        f"Выполнить на <b>{server.name}</b>:\n<code>{action.command}</code>",
        reply_markup=confirm_keyboard(token),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("unitlogs:"), MenuState.units)
async def cb_unitlogs(
    callback: CallbackQuery, state: FSMContext, config: AppConfig, pool: SshPool
) -> None:
    index = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    units = data.get("units", [])
    server = config.server(data.get("server_id", ""))
    if server is None or index >= len(units):
        await callback.answer("Список устарел", show_alert=True)
        return
    await run_command(
        pool,
        server,
        logs_command(units[index]),
        config.defaults.output_max_lines,
        callback.message.answer,
    )
    await callback.answer()
```

`src/bot/handlers/updates.py`:

```python
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.actions.updates import (
    UPGRADABLE_COMMAND,
    parse_upgradable,
    reboot_action,
    upgrade_action,
)
from bot.config import AppConfig
from bot.keyboards import confirm_keyboard
from bot.security import ConfirmationStore
from bot.ssh.pool import ServerUnavailable, SshPool

router = Router()


@router.callback_query(F.data.startswith("updates:"))
async def cb_updates(callback: CallbackQuery, config: AppConfig, pool: SshPool) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    try:
        result = await pool.run(server, UPGRADABLE_COMMAND)
    except ServerUnavailable as exc:
        await callback.answer(f"Недоступен: {exc}", show_alert=True)
        return
    packages = parse_upgradable(result.stdout)
    if not packages:
        await callback.message.answer("Обновлений нет")
        await callback.answer()
        return
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Обновить", callback_data=f"upgrade:{server_id}")]
        ]
    )
    text = "Доступны обновления:\n" + "\n".join(f"• {name}" for name in packages)
    await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("upgrade:"))
async def cb_upgrade(
    callback: CallbackQuery, config: AppConfig, confirmations: ConfirmationStore
) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    action = upgrade_action(server)
    token = confirmations.create(callback.from_user.id, action)
    await callback.message.answer(
        f"Обновить пакеты на <b>{server.name}</b>?\n<code>{action.command}</code>",
        reply_markup=confirm_keyboard(token),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reboot:"))
async def cb_reboot(
    callback: CallbackQuery, config: AppConfig, confirmations: ConfirmationStore
) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    action = reboot_action(server)
    token = confirmations.create(callback.from_user.id, action)
    await callback.message.answer(
        f"Перезагрузить <b>{server.name}</b>?\n<code>{action.command}</code>",
        reply_markup=confirm_keyboard(token),
        parse_mode="HTML",
    )
    await callback.answer()
```

`src/bot/handlers/docker.py`:

```python
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.actions.base import InvalidArgument
from bot.actions.docker import docker_logs_command, docker_restart_action
from bot.collectors.docker import CollectorError, collect_docker
from bot.config import AppConfig
from bot.handlers.common import MenuState, run_command
from bot.keyboards import confirm_keyboard, docker_keyboard
from bot.security import ConfirmationStore
from bot.ssh.pool import ServerUnavailable, SshPool

router = Router()


@router.callback_query(F.data.startswith("docker:"))
async def cb_docker(
    callback: CallbackQuery, state: FSMContext, config: AppConfig, pool: SshPool
) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    try:
        containers = await collect_docker(pool, server)
    except (ServerUnavailable, CollectorError) as exc:
        await callback.answer(f"Ошибка: {exc}", show_alert=True)
        return
    names = [container.name for container in containers]
    if not names:
        await callback.message.answer("Контейнеров нет")
        await callback.answer()
        return
    await state.set_state(MenuState.docker)
    await state.update_data(server_id=server_id, containers=names)
    await callback.message.answer("Контейнеры:", reply_markup=docker_keyboard(names))
    await callback.answer()


@router.callback_query(F.data.startswith("dlog:"), MenuState.docker)
async def cb_dlog(
    callback: CallbackQuery, state: FSMContext, config: AppConfig, pool: SshPool
) -> None:
    index = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    names = data.get("containers", [])
    server = config.server(data.get("server_id", ""))
    if server is None or index >= len(names):
        await callback.answer("Список устарел", show_alert=True)
        return
    await run_command(
        pool,
        server,
        docker_logs_command(names[index]),
        config.defaults.output_max_lines,
        callback.message.answer,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("drestart:"), MenuState.docker)
async def cb_drestart(
    callback: CallbackQuery,
    state: FSMContext,
    config: AppConfig,
    confirmations: ConfirmationStore,
) -> None:
    index = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    names = data.get("containers", [])
    server = config.server(data.get("server_id", ""))
    if server is None or index >= len(names):
        await callback.answer("Список устарел", show_alert=True)
        return
    try:
        action = docker_restart_action(server, names[index])
    except InvalidArgument as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    token = confirmations.create(callback.from_user.id, action)
    await callback.message.answer(
        f"Выполнить на <b>{server.name}</b>:\n<code>{action.command}</code>",
        reply_markup=confirm_keyboard(token),
        parse_mode="HTML",
    )
    await callback.answer()
```

`src/bot/handlers/confirm.py`:

```python
from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.config import AppConfig
from bot.handlers.common import run_command
from bot.security import ConfirmationStore
from bot.ssh.pool import SshPool

router = Router()


@router.callback_query(F.data.startswith("confirm:"))
async def cb_confirm(
    callback: CallbackQuery,
    config: AppConfig,
    pool: SshPool,
    confirmations: ConfirmationStore,
) -> None:
    token = callback.data.split(":", 1)[1]
    action = confirmations.take(callback.from_user.id, token)
    if action is None:
        await callback.answer("Подтверждение истекло или недействительно", show_alert=True)
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    server = config.server(action.server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    await callback.answer("Выполняю…")
    await run_command(
        pool,
        server,
        action.command,
        config.defaults.output_max_lines,
        callback.message.answer,
    )


@router.callback_query(F.data.startswith("cancel:"))
async def cb_cancel(callback: CallbackQuery, confirmations: ConfirmationStore) -> None:
    token = callback.data.split(":", 1)[1]
    confirmations.take(callback.from_user.id, token)
    await callback.message.edit_text("❌ Отменено")
    await callback.answer()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_handlers_wiring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/handlers/services.py src/bot/handlers/updates.py src/bot/handlers/docker.py src/bot/handlers/confirm.py tests/test_handlers_wiring.py
git commit -m "feat: add services, updates, docker and confirmation handlers"
```

---

### Task 13: Handlers for shell and alerts

**Files:**
- Create: `src/bot/handlers/shell.py`
- Create: `src/bot/handlers/alerts.py`
- Modify: `tests/test_handlers_wiring.py`

**Interfaces:**
- Consumes: `ShellState` (Task 11), `AlertRuntime` (Task 8), `shell_action` (Task 6).
- Produces: routers `shell.router`, `alerts.router`.

- [ ] **Step 1: Extend the failing test**

Append to `tests/test_handlers_wiring.py`:

```python
from bot.handlers import alerts as alerts_module
from bot.handlers import shell as shell_module


def test_shell_and_alerts_routers():
    assert isinstance(shell_module.router, Router)
    assert isinstance(alerts_module.router, Router)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_handlers_wiring.py -v`
Expected: FAIL (ImportError: cannot import name 'shell')

- [ ] **Step 3: Write implementation**

`src/bot/handlers/shell.py`:

```python
from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.actions.shell import shell_action
from bot.config import AppConfig
from bot.handlers.common import ShellState
from bot.keyboards import confirm_keyboard
from bot.security import ConfirmationStore

router = Router()


async def start_shell(
    message: Message, state: FSMContext, config: AppConfig, server_id: str
) -> None:
    if not server_id:
        await message.answer("Использование: /shell <server_id>")
        return
    server = config.server(server_id.strip())
    if server is None:
        await message.answer("Сервер не найден")
        return
    await state.set_state(ShellState.waiting_command)
    await state.update_data(server_id=server.id)
    await message.answer(f"Введи команду для {server.name}:")


@router.message(Command("shell"))
async def cmd_shell(message: Message, state: FSMContext, config: AppConfig) -> None:
    parts = (message.text or "").split(maxsplit=1)
    server_id = parts[1] if len(parts) > 1 else ""
    await start_shell(message, state, config, server_id)


@router.callback_query(F.data.startswith("shell:"))
async def cb_shell(callback: CallbackQuery, state: FSMContext, config: AppConfig) -> None:
    server_id = callback.data.split(":", 1)[1]
    await start_shell(callback.message, state, config, server_id)
    await callback.answer()


@router.message(ShellState.waiting_command)
async def on_shell_command(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    confirmations: ConfirmationStore,
) -> None:
    data = await state.get_data()
    server = config.server(data.get("server_id", ""))
    if server is None:
        await message.answer("Сервер не найден")
        await state.clear()
        return
    action = shell_action(server, message.text or "")
    token = confirmations.create(message.from_user.id, action)
    await message.answer(
        f"Выполнить на <b>{server.name}</b>:\n<code>{html.escape(action.command)}</code>",
        reply_markup=confirm_keyboard(token),
        parse_mode="HTML",
    )
    await state.clear()
```

`src/bot/handlers/alerts.py`:

```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.alerts.engine import AlertRuntime
from bot.config import AppConfig

router = Router()


def alerts_text(config: AppConfig, runtime: AlertRuntime) -> str:
    thresholds = config.alerts.thresholds
    state = "включены" if runtime.enabled else "выключены"
    offline = "да" if thresholds.offline else "нет"
    return (
        f"Алерты: {state}\n"
        f"CPU > {thresholds.cpu_percent}%\n"
        f"RAM > {thresholds.ram_percent}%\n"
        f"Диск > {thresholds.disk_percent}%\n"
        f"Load/CPU > {thresholds.load_per_cpu}\n"
        f"Offline: {offline}\n"
        f"Интервал: {config.alerts.interval}с, cooldown: {config.alerts.cooldown}с"
    )


def alerts_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    label = "🔕 Выключить" if enabled else "🔔 Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data="alerts:toggle")]
        ]
    )


@router.message(Command("alerts"))
async def cmd_alerts(
    message: Message, config: AppConfig, runtime: AlertRuntime
) -> None:
    await message.answer(
        alerts_text(config, runtime), reply_markup=alerts_keyboard(runtime.enabled)
    )


@router.callback_query(F.data == "alerts:toggle")
async def cb_alerts(
    callback: CallbackQuery, config: AppConfig, runtime: AlertRuntime
) -> None:
    runtime.enabled = not runtime.enabled
    await callback.message.edit_text(
        alerts_text(config, runtime), reply_markup=alerts_keyboard(runtime.enabled)
    )
    await callback.answer()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_handlers_wiring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/bot/handlers/shell.py src/bot/handlers/alerts.py tests/test_handlers_wiring.py
git commit -m "feat: add shell and alerts handlers"
```

---

### Task 14: Application wiring and alert job

**Files:**
- Create: `src/bot/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `build_dispatcher(config, pool, confirmations, runtime) -> Dispatcher`
  - `async poll_and_alert(bot, config, pool, engine, runtime) -> None`
  - `async run(config: AppConfig) -> None`
  - `main() -> None`

- [ ] **Step 1: Write the failing test**

`tests/test_main.py`:

```python
from pathlib import Path

from bot.alerts.engine import AlertEngine, AlertRuntime
from bot.config import AppConfig, Thresholds
from bot.main import build_dispatcher, poll_and_alert
from bot.security import ConfirmationStore
from bot.ssh.pool import CommandResult

FIXTURE = Path(__file__).parent / "fixtures" / "system_output.txt"


def make_config() -> AppConfig:
    return AppConfig(
        telegram={"token": "t", "allowed_users": [1]},
        alerts={"interval": 60, "cooldown": 300, "thresholds": {"cpu_percent": 1}},
        servers=[
            {
                "id": "web1",
                "name": "Web 1",
                "host": "1.2.3.4",
                "user": "admin",
                "auth": {"type": "password", "password": "secret"},
            }
        ],
    )


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text, parse_mode=None) -> None:
        self.sent.append((chat_id, text))


class FakePool:
    def __init__(self, result: CommandResult) -> None:
        self._result = result

    async def run(self, server, command, timeout=None) -> CommandResult:
        return self._result


def test_build_dispatcher_registers_routers():
    config = make_config()
    dispatcher = build_dispatcher(
        config,
        FakePool(CommandResult("", "", 0, 0.0)),
        ConfirmationStore(),
        AlertRuntime(),
    )

    assert dispatcher is not None


async def test_poll_and_alert_sends_alert():
    config = make_config()
    bot = FakeBot()
    pool = FakePool(CommandResult(FIXTURE.read_text(encoding="utf-8"), "", 0, 0.1))
    engine = AlertEngine(Thresholds(cpu_percent=1), 300.0)
    runtime = AlertRuntime(enabled=True)

    await poll_and_alert(bot, config, pool, engine, runtime)

    assert len(bot.sent) == 1
    assert bot.sent[0][0] == 1
    assert "Web 1" in bot.sent[0][1]


async def test_poll_and_alert_respects_disabled_runtime():
    config = make_config()
    bot = FakeBot()
    pool = FakePool(CommandResult(FIXTURE.read_text(encoding="utf-8"), "", 0, 0.1))
    engine = AlertEngine(Thresholds(cpu_percent=1), 300.0)

    await poll_and_alert(bot, config, pool, engine, AlertRuntime(enabled=False))

    assert bot.sent == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'bot.main')

- [ ] **Step 3: Write implementation**

`src/bot/main.py`:

```python
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.alerts.engine import AlertEngine, AlertRuntime
from bot.collectors.system import CollectorError, collect_system
from bot.config import AppConfig, load_config
from bot.formatting import format_alert
from bot.handlers import (
    alerts,
    confirm,
    docker,
    services,
    shell,
    start,
    status,
    updates,
    servers,
)
from bot.handlers.common import DependenciesMiddleware
from bot.security import ConfirmationStore, WhitelistMiddleware
from bot.ssh.pool import ServerUnavailable, SshPool

logger = logging.getLogger(__name__)


def build_dispatcher(
    config: AppConfig,
    pool: SshPool,
    confirmations: ConfirmationStore,
    runtime: AlertRuntime,
) -> Dispatcher:
    dispatcher = Dispatcher()
    whitelist = WhitelistMiddleware(config.telegram.allowed_users)
    dispatcher.message.middleware(whitelist)
    dispatcher.callback_query.middleware(whitelist)

    dependencies = DependenciesMiddleware(config, pool, confirmations, runtime)
    dispatcher.message.middleware(dependencies)
    dispatcher.callback_query.middleware(dependencies)

    for module in (
        start,
        servers,
        status,
        services,
        updates,
        docker,
        shell,
        alerts,
        confirm,
    ):
        dispatcher.include_router(module.router)
    return dispatcher


async def poll_and_alert(
    bot: Bot,
    config: AppConfig,
    pool: SshPool,
    engine: AlertEngine,
    runtime: AlertRuntime,
) -> None:
    if not runtime.enabled:
        return
    for server in config.servers:
        try:
            metrics = await collect_system(pool, server)
        except (ServerUnavailable, CollectorError) as exc:
            logger.warning("Poll failed for %s: %s", server.id, exc)
            events = engine.evaluate_offline(server.id)
        else:
            events = engine.mark_online(server.id) + engine.evaluate(server.id, metrics)
        for event in events:
            message = format_alert(event, server)
            for user_id in config.telegram.allowed_users:
                await bot.send_message(user_id, message, parse_mode="HTML")


async def run(config: AppConfig) -> None:
    bot = Bot(config.telegram.token)
    pool = SshPool(config.defaults.ssh)
    confirmations = ConfirmationStore(ttl=60.0)
    runtime = AlertRuntime(enabled=config.alerts.enabled)
    engine = AlertEngine(config.alerts.thresholds, config.alerts.cooldown)
    dispatcher = build_dispatcher(config, pool, confirmations, runtime)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_and_alert,
        "interval",
        seconds=config.alerts.interval,
        args=[bot, config, pool, engine, runtime],
    )
    scheduler.start()
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await pool.aclose()
        await bot.session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = load_config("config.yaml")
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/bot/main.py tests/test_main.py
git commit -m "feat: wire bot, scheduler and alert polling"
```

---

### Task 15: Example config, systemd unit, README

**Files:**
- Create: `config.example.yaml`
- Create: `deploy/management-bot.service`
- Create: `README.md`
- Create: `tests/test_example_config.py`

**Interfaces:**
- Consumes: `load_config` (Task 2).
- Produces: deployable example configuration and documentation.

- [ ] **Step 1: Write the failing test**

`tests/test_example_config.py`:

```python
from pathlib import Path

from bot.config import load_config

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config.example.yaml"


def test_example_config_is_valid():
    env = {
        "TG_BOT_TOKEN": "token",
        "WEB1_PASS": "pass",
        "DB1_PASSPHRASE": "phrase",
    }
    config = load_config(EXAMPLE, env)

    assert [server.id for server in config.servers] == ["web1", "db1"]
    assert config.servers[0].auth.type == "password"
    assert config.servers[1].auth.type == "key"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_example_config.py -v`
Expected: FAIL (FileNotFoundError: config.example.yaml)

- [ ] **Step 3: Create the example config**

`config.example.yaml`:

```yaml
telegram:
  token: "${TG_BOT_TOKEN}"
  allowed_users: [123456789]

defaults:
  ssh:
    connect_timeout: 10
    command_timeout: 30
    max_concurrency: 8
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
    auth:
      type: password
      password: "${WEB1_PASS}"
    tags: [web, prod]
  - id: db1
    name: "DB 1"
    host: 5.6.7.8
    port: 22
    user: deploy
    auth:
      type: key
      key_path: "~/.ssh/db1"
      passphrase: "${DB1_PASSPHRASE}"
    tags: [db, prod]
```

- [ ] **Step 4: Create the systemd unit**

`deploy/management-bot.service`:

```ini
[Unit]
Description=Telegram VPS Manager Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/management
EnvironmentFile=/opt/management/bot.env
ExecStart=/opt/management/.venv/bin/python -m bot.main
Restart=on-failure
RestartSec=5
User=management

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 5: Create the README**

`README.md`:

```markdown
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
- Секреты хранятся в `config.yaml` только как `${ENV}`-ссылки.
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
sudo useradd --system --home /opt/management management
sudo mkdir -p /opt/management
sudo cp -r src pyproject.toml config.example.yaml /opt/management/
sudo cp config.yaml /opt/management/
sudo cp deploy/management-bot.service /etc/systemd/system/
sudo chmod 600 /opt/management/config.yaml
sudo -u management python3.11 -m venv /opt/management/.venv
sudo -u management /opt/management/.venv/bin/pip install /opt/management
sudo systemctl daemon-reload
sudo systemctl enable --now management-bot
```

`/opt/management/bot.env` — файл с секретами в формате `KEY=value`,
доступный только пользователю `management` (chmod 600).
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_example_config.py -v`
Expected: PASS

- [ ] **Step 7: Run the full suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add config.example.yaml deploy/management-bot.service README.md tests/test_example_config.py
git commit -m "docs: add example config, systemd unit and README"
```

---

## Self-Review

- **Spec coverage:** топология/SSH (Task 3), конфиг + оба типа auth (Task 2),
  whitelist и подтверждения (Task 7), метрики (Tasks 4, 11), сервисы (Tasks 6, 12),
  обновления/reboot (Tasks 6, 12), Docker (Tasks 5, 6, 12), shell (Tasks 6, 13),
  алерты (Tasks 8, 14), форматирование/клавиатуры (Tasks 9, 10), деплой (Task 15).
- **Placeholder scan:** шаблонов TBD/TODO нет; каждый шаг содержит код или команду.
- **Type consistency:** `PreparedAction`, `CommandResult`, `SystemMetrics`,
  `AlertEvent`, `AlertRuntime`, `ConfirmationStore`, `SshPool.run`, `parse_callback`
  используются с одинаковыми сигнатурами во всех задачах.
- **Известные отступления от спеки:** файлы handlers сгруппированы по смыслу
  (spec перечислял отдельный файл на команду); SQLite отсутствует — состояние
  алертов в памяти; `known_hosts=None` задокументирован как осознанный компромисс.

