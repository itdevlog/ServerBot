from __future__ import annotations

import re

from bot.actions.base import PreparedAction
from bot.config import ServerConfig

UPGRADABLE_COMMAND = "apt list --upgradable 2>/dev/null"
UPGRADE_COMMAND = "DEBIAN_FRONTEND=noninteractive apt-get -y upgrade"
REBOOT_COMMAND = "systemctl reboot"

_UPGRADABLE_RE = re.compile(
    r"^([a-z0-9][a-z0-9+.-]*)/\S+\s+\S+\s+\S+"
)


def parse_upgradable(text: str) -> list[str]:
    packages: list[str] = []
    for line in text.splitlines():
        match = _UPGRADABLE_RE.match(line)
        if match:
            packages.append(match.group(1))
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
