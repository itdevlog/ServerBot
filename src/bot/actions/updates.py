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
