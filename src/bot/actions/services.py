from __future__ import annotations

import re
from dataclasses import dataclass

from bot.actions.base import InvalidArgument, PreparedAction
from bot.config import ServerConfig

_UNIT_RE = re.compile(r"[A-Za-z0-9@_.-]+")

LIST_UNITS_COMMAND = (
    "systemctl list-units --type=service --state=running --no-pager --plain"
)


@dataclass
class UnitInfo:
    name: str
    load: str
    active: str
    sub: str


def validate_unit(name: str) -> str:
    if not name or not _UNIT_RE.fullmatch(name):
        raise InvalidArgument(f"Invalid unit: {name!r}")
    return name


def service_action(server: ServerConfig, unit: str, verb: str) -> PreparedAction:
    if verb not in {"start", "stop", "restart"}:
        raise InvalidArgument(f"Invalid verb: {verb!r}")
    safe_unit = validate_unit(unit)
    return PreparedAction(
        server_id=server.id,
        title=f"{verb} {safe_unit}",
        command=f"systemctl {verb} {safe_unit}",
        dangerous=verb in {"stop", "restart"},
    )


def parse_systemctl_units(text: str) -> list[UnitInfo]:
    units: list[UnitInfo] = []
    for line in text.splitlines():
        columns = line.split()
        if len(columns) < 4:
            continue
        if not columns[0].endswith(".service"):
            continue
        units.append(
            UnitInfo(
                name=columns[0],
                load=columns[1],
                active=columns[2],
                sub=columns[3],
            )
        )
    return units


def logs_command(unit: str, lines: int = 50) -> str:
    safe_unit = validate_unit(unit)
    return f"journalctl -u {safe_unit} -n {int(lines)} --no-pager"
