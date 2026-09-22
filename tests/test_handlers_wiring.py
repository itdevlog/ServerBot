from aiogram import Router

from bot.handlers import confirm, docker, services, updates


def test_new_routers_are_routers():
    for module in (services, updates, docker, confirm):
        assert isinstance(module.router, Router)
