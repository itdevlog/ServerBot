from pathlib import Path

import pytest

from bot.config import AppConfig, ConfigError, expand_env, load_config

VALID = """
telegram:
  token: "${TG_TOKEN}"
  allowed_users: [42]
servers:
  - id: web1
    name: "Web 1"
    host: 1.2.3.4
    user: admin
    auth: { type: password, password: "${WEB_PASS}" }
  - id: db1
    name: "DB 1"
    host: 5.6.7.8
    user: deploy
    auth: { type: key, key_path: "~/.ssh/db1", passphrase: "${DB_PASS}" }
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_expand_env_substitutes_known_variable():
    assert expand_env("a=${X}", {"X": "1"}) == "a=1"


def test_expand_env_raises_on_missing_variable():
    with pytest.raises(ConfigError, match="MISSING"):
        expand_env("${MISSING}", {})


def test_load_config_full(tmp_path):
    env = {"TG_TOKEN": "t", "WEB_PASS": "p", "DB_PASS": "k"}
    config = load_config(write(tmp_path, VALID), env)

    assert isinstance(config, AppConfig)
    assert config.telegram.token == "t"
    assert config.telegram.allowed_users == [42]
    assert config.server("web1").auth.password == "p"
    assert config.server("db1").auth.key_path == "~/.ssh/db1"
    assert config.server("db1").auth.passphrase == "k"
    assert config.server("missing") is None
    assert config.defaults.output_max_lines == 40
    assert config.alerts.thresholds.cpu_percent == 85.0


def test_password_auth_requires_password(tmp_path):
    text = """
telegram: { token: t, allowed_users: [1] }
servers:
  - id: a
    name: a
    host: h
    user: u
    auth: { type: password }
"""
    with pytest.raises(ValueError, match="password"):
        load_config(write(tmp_path, text), {})


def test_key_auth_requires_key_path(tmp_path):
    text = """
telegram: { token: t, allowed_users: [1] }
servers:
  - id: a
    name: a
    host: h
    user: u
    auth: { type: key }
"""
    with pytest.raises(ValueError, match="key_path"):
        load_config(write(tmp_path, text), {})
