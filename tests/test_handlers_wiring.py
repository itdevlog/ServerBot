from aiogram import Router

from bot.handlers import confirm, docker, services, updates


def test_new_routers_are_routers():
    for module in (services, updates, docker, confirm):
        assert isinstance(module.router, Router)


from bot.handlers import alerts as alerts_module
from bot.handlers import shell as shell_module


def test_shell_and_alerts_routers():
    assert isinstance(shell_module.router, Router)
    assert isinstance(alerts_module.router, Router)
