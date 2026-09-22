from pathlib import Path

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


def test_parse_docker_ps_skips_malformed_lines():
    text = "onlyonecolumn\nc1a2b3d4e5f6\tweb\tnginx:1.27\tUp 3 days\n"

    containers = parse_docker_ps(text)

    assert [container.name for container in containers] == ["web"]


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
