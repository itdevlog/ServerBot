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
