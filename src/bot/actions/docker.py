from __future__ import annotations

from bot.actions.base import PreparedAction, validate_positive_int, validate_token
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
    safe_lines = validate_positive_int(lines)
    return f"docker logs --tail {safe_lines} {safe_name}"
