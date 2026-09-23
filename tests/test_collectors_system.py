import asyncio
from pathlib import Path

import pytest

from bot.collectors.system import (
    CollectorError,
    SYSTEM_COMMAND,
    collect_system,
    parse_cpu_stat,
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
    assert parse_fixture().cpu_percent == 20.0


def test_parse_cpu_stat_is_locale_independent():
    first = "cpu  100 0 100 800 0 0 0 0 0 0"
    second = "cpu  200 0 200 1600 0 0 0 0 0 0"

    assert parse_cpu_stat(first, second) == 20.0


def test_parse_cpu_stat_raises_on_zero_delta():
    line = "cpu  100 0 100 800 0 0 0 0 0 0"

    with pytest.raises(CollectorError):
        parse_cpu_stat(line, line)


def test_parse_cpu_stat_raises_on_missing_values():
    with pytest.raises(CollectorError):
        parse_cpu_stat("cpu  1 2 3", "cpu  1 2 3")


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


def test_malformed_numeric_section_raises_collector_error():
    text = FIXTURE.read_text(encoding="utf-8").replace("###NPROC\n4", "###NPROC\nnope")

    with pytest.raises(CollectorError):
        parse_system_output(text)


def test_malformed_load_section_raises_collector_error():
    text = FIXTURE.read_text(encoding="utf-8").replace(
        "###LOAD\n0.15 0.20 0.25 1/234 5678", "###LOAD\ngarbage"
    )

    with pytest.raises(CollectorError):
        parse_system_output(text)


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


def test_system_command_falls_back_when_nproc_missing():
    assert "grep -c ^processor /proc/cpuinfo" in SYSTEM_COMMAND


def test_system_command_falls_back_when_hostname_missing():
    assert "cat /proc/sys/kernel/hostname" in SYSTEM_COMMAND


def test_busybox_missing_hostname_section_parses():
    text = FIXTURE.read_text(encoding="utf-8").replace(
        "###HOST\nvps-web1", "###HOST\n"
    )

    metrics = parse_system_output(text)

    assert metrics.hostname == "unknown"


def test_nproc_fallback_output_parses(monkeypatch):
    busybox_output = FIXTURE.read_text(encoding="utf-8").replace(
        "###NPROC\n4", "###NPROC\n2"
    )
    pool = FakePool(CommandResult(busybox_output, "", 0, 0.1))

    metrics = asyncio.run(collect_system(pool, make_server()))

    assert metrics.cpu_count == 2
