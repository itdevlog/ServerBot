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
