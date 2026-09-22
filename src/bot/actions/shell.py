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
