from pathlib import Path

from bot.config import load_config

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config.example.yaml"


def test_example_config_is_valid():
    env = {
        "TG_BOT_TOKEN": "token",
        "WEB1_PASS": "pass",
        "DB1_PASSPHRASE": "phrase",
    }
    config = load_config(EXAMPLE, env)

    assert [server.id for server in config.servers] == ["web1", "db1"]
    assert config.servers[0].auth.type == "password"
    assert config.servers[1].auth.type == "key"
