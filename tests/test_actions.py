from pathlib import Path

import pytest

from bot.actions import docker as docker_actions
from bot.actions import services, updates
from bot.actions.base import InvalidArgument, PreparedAction, validate_token
from bot.actions.shell import shell_action
from bot.config import ServerConfig

FIXTURES = Path(__file__).parent / "fixtures"


def make_server() -> ServerConfig:
    return ServerConfig(
        id="web1",
        name="Web 1",
        host="1.2.3.4",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


def test_validate_token_accepts_safe_values():
    assert validate_token("nginx.service", "unit") == "nginx.service"
    assert validate_token("my-container_1") == "my-container_1"


def test_validate_token_rejects_shell_metacharacters():
    for bad in ["a; rm -rf /", "a && b", "a|b", "a$(whoami)", "a b"]:
        with pytest.raises(InvalidArgument):
            validate_token(bad)


def test_service_action_is_dangerous():
    action = services.service_action(make_server(), "nginx", "restart")

    assert isinstance(action, PreparedAction)
    assert action.dangerous is True
    assert action.command == "systemctl restart nginx"
    assert action.server_id == "web1"


def test_service_action_rejects_bad_unit():
    with pytest.raises(InvalidArgument):
        services.service_action(make_server(), "nginx; reboot", "restart")


def test_parse_systemctl_units():
    units = services.parse_systemctl_units(
        (FIXTURES / "systemctl_units.txt").read_text(encoding="utf-8")
    )

    assert [u.name for u in units] == ["nginx.service", "ssh.service", "cron.service"]
    assert units[0].active == "active"


def test_logs_command():
    assert services.logs_command("nginx", 20) == "journalctl -u nginx -n 20 --no-pager"


def test_parse_upgradable():
    packages = updates.parse_upgradable(
        (FIXTURES / "apt_upgradable.txt").read_text(encoding="utf-8")
    )

    assert packages == ["nginx", "openssl"]


def test_upgrade_action_is_dangerous():
    action = updates.upgrade_action(make_server())

    assert action.dangerous is True
    assert action.command == updates.UPGRADE_COMMAND


def test_reboot_action_is_dangerous():
    action = updates.reboot_action(make_server())

    assert action.dangerous is True
    assert action.command == updates.REBOOT_COMMAND


def test_docker_restart_action():
    action = docker_actions.docker_restart_action(make_server(), "web-nginx")

    assert action.command == "docker restart web-nginx"
    assert action.dangerous is True


def test_docker_restart_rejects_bad_name():
    with pytest.raises(InvalidArgument):
        docker_actions.docker_restart_action(make_server(), "web; reboot")


def test_docker_logs_command():
    assert (
        docker_actions.docker_logs_command("web-nginx", 30)
        == "docker logs --tail 30 web-nginx"
    )


def test_shell_action_is_dangerous_and_keeps_command():
    action = shell_action(make_server(), "df -h && uptime")

    assert action.dangerous is True
    assert action.command == "df -h && uptime"
