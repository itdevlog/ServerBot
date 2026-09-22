from __future__ import annotations

import os
import re
from pathlib import Path
from collections.abc import Mapping
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(Exception):
    pass


def expand_env(text: str, env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in source:
            raise ConfigError(f"Missing environment variable: {name}")
        return source[name]

    return _ENV_RE.sub(replace, text)


class SshAuth(BaseModel):
    type: Literal["password", "key"]
    password: str | None = None
    key_path: str | None = None
    passphrase: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "SshAuth":
        if self.type == "password" and not self.password:
            raise ValueError("password auth requires 'password'")
        if self.type == "key" and not self.key_path:
            raise ValueError("key auth requires 'key_path'")
        return self


class ServerConfig(BaseModel):
    id: str
    name: str
    host: str
    port: int = 22
    user: str
    auth: SshAuth
    tags: list[str] = Field(default_factory=list)


class SshDefaults(BaseModel):
    connect_timeout: int = 10
    command_timeout: int = 30
    max_concurrency: int = Field(default=8, gt=0)


class Defaults(BaseModel):
    ssh: SshDefaults = Field(default_factory=SshDefaults)
    output_max_lines: int = 40


class Thresholds(BaseModel):
    cpu_percent: float = 85.0
    ram_percent: float = 90.0
    disk_percent: float = 85.0
    load_per_cpu: float = 2.0
    offline: bool = True


class AlertsConfig(BaseModel):
    enabled: bool = True
    interval: int = 60
    cooldown: int = 300
    thresholds: Thresholds = Field(default_factory=Thresholds)


class TelegramConfig(BaseModel):
    token: str
    allowed_users: list[int]


class AppConfig(BaseModel):
    telegram: TelegramConfig
    defaults: Defaults = Field(default_factory=Defaults)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    servers: list[ServerConfig]

    @model_validator(mode="after")
    def _unique_server_ids(self) -> "AppConfig":
        seen: set[str] = set()
        for server in self.servers:
            if server.id in seen:
                raise ValueError(f"duplicate server id: {server.id}")
            seen.add(server.id)
        return self

    def server(self, server_id: str) -> ServerConfig | None:
        for server in self.servers:
            if server.id == server_id:
                return server
        return None


def _substitute_env(value, env: Mapping[str, str] | None):
    if isinstance(value, str):
        return expand_env(value, env)
    if isinstance(value, dict):
        return {key: _substitute_env(item, env) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute_env(item, env) for item in value]
    return value


def load_config(path: str | Path, env: Mapping[str, str] | None = None) -> AppConfig:
    raw = Path(path).read_text(encoding="utf-8")
    data = _substitute_env(yaml.safe_load(raw), env)
    return AppConfig.model_validate(data)
