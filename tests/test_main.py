from pathlib import Path

from bot.alerts.engine import AlertEngine, AlertRuntime
from bot.collectors.system import CollectorError
from bot.config import AppConfig, Thresholds
from bot.main import build_dispatcher, poll_and_alert
from bot.security import ConfirmationStore
from bot.ssh.pool import CommandResult, ServerUnavailable

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


class RaisingPool:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def run(self, server, command, timeout=None) -> CommandResult:
        raise self._exc


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


async def test_poll_and_alert_survives_send_failure():
    config = make_config()
    config.telegram.allowed_users = [1, 2]

    class FlakyBot(FakeBot):
        async def send_message(self, chat_id, text, parse_mode=None) -> None:
            if chat_id == 1:
                raise RuntimeError("blocked")
            self.sent.append((chat_id, text))

    bot = FlakyBot()
    pool = FakePool(CommandResult(FIXTURE.read_text(encoding="utf-8"), "", 0, 0.1))
    engine = AlertEngine(Thresholds(cpu_percent=1), 300.0)

    await poll_and_alert(bot, config, pool, engine, AlertRuntime(enabled=True))

    assert bot.sent == [(2, bot.sent[0][1])]


async def test_collector_error_does_not_alert_offline():
    config = make_config()
    bot = FakeBot()
    pool = RaisingPool(CollectorError("Missing section NPROC in system output"))
    engine = AlertEngine(Thresholds(offline=True), 300.0)

    await poll_and_alert(bot, config, pool, engine, AlertRuntime(enabled=True))

    assert bot.sent == []
    assert "web1" not in engine._active


async def test_server_unavailable_alerts_offline_after_threshold():
    config = make_config()
    bot = FakeBot()
    pool = RaisingPool(ServerUnavailable("network unreachable"))
    engine = AlertEngine(Thresholds(offline=True), 300.0)

    for _ in range(AlertEngine.OFFLINE_THRESHOLD):
        await poll_and_alert(bot, config, pool, engine, AlertRuntime(enabled=True))

    assert len(bot.sent) == 1
    assert "недоступен" in bot.sent[0][1]
