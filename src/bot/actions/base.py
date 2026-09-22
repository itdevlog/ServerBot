from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[A-Za-z0-9@_.:/-]+")


class InvalidArgument(Exception):
    pass


@dataclass(frozen=True)
class PreparedAction:
    server_id: str
    title: str
    command: str
    dangerous: bool


def validate_token(value: str, field: str = "argument") -> str:
    if not value or not _TOKEN_RE.fullmatch(value):
        raise InvalidArgument(f"Invalid {field}: {value!r}")
    return value


def validate_positive_int(value: int, field: str = "lines") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvalidArgument(f"Invalid {field}: {value!r}")
    return value
