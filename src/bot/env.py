from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, MutableMapping

DEFAULT_ENV_FILES = ("bot.env", ".env")


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values


def load_env_file(
    paths: Iterable[str] = DEFAULT_ENV_FILES,
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    target = os.environ if environ is None else environ
    loaded: dict[str, str] = {}
    for name in paths:
        path = Path(name)
        if not path.is_file():
            continue
        for key, value in parse_env(path.read_text(encoding="utf-8")).items():
            if key not in target:
                target[key] = value
                loaded[key] = value
    return loaded
