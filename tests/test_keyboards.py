from bot.config import ServerConfig
from bot.keyboards import (
    confirm_keyboard,
    docker_keyboard,
    server_menu_keyboard,
    servers_keyboard,
    unit_actions_keyboard,
    units_keyboard,
)


def make_server() -> ServerConfig:
    return ServerConfig(
        id="web1",
        name="Web 1",
        host="1.2.3.4",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


def callbacks(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_servers_keyboard():
    assert callbacks(servers_keyboard([make_server()])) == ["menu:web1"]


def test_server_menu_keyboard_contains_all_actions():
    data = callbacks(server_menu_keyboard("web1"))

    assert "metrics:web1" in data
    assert "units:web1" in data
    assert "updates:web1" in data
    assert "docker:web1" in data
    assert "shell:web1" in data
    assert "reboot:web1" in data


def test_units_keyboard_indexes_units():
    assert callbacks(units_keyboard(["nginx", "ssh"])) == ["unit:0", "unit:1"]


def test_unit_actions_keyboard():
    data = callbacks(unit_actions_keyboard(2))

    assert data == ["unitact:restart:2", "unitact:stop:2", "unitact:start:2", "unitlogs:2"]


def test_confirm_keyboard():
    data = callbacks(confirm_keyboard("abcd"))

    assert data == ["confirm:abcd", "cancel:abcd"]


def test_docker_keyboard():
    assert callbacks(docker_keyboard(["web"])) == ["dlog:0", "drestart:0"]
