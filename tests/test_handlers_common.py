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
