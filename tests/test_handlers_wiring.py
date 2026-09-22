from aiogram import Router

from bot.config import AppConfig
from bot.handlers import alerts as alerts_module
from bot.handlers import confirm, docker, services, shell as shell_module, updates


def test_new_routers_are_routers():
    for module in (services, updates, docker, confirm):
        assert isinstance(module.router, Router)


def test_shell_and_alerts_routers():
    assert isinstance(shell_module.router, Router)
    assert isinstance(alerts_module.router, Router)


class FakeMessage:
    def __init__(self) -> None:
        self.answers: list[tuple[str, object]] = []

    async def answer(self, text, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


class FakeCallback:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = FakeMessage()
        self.answers: list[tuple[object, bool]] = []

    async def answer(self, text=None, show_alert=False) -> None:
        self.answers.append((text, show_alert))


def make_config() -> AppConfig:
    return AppConfig(
        telegram={"token": "t", "allowed_users": [1]},
        servers=[
            {
                "id": "web1",
                "name": "Web 1",
                "host": "1.2.3.4",
                "user": "admin",
                "auth": {"type": "password", "password": "secret"},
            }
        ],
    )


async def test_cb_menu_opens_server_panel():
    from bot.handlers import servers as servers_module
    from bot.keyboards import server_menu_keyboard

    callback = FakeCallback("menu:web1")
    await servers_module.cb_menu(callback, make_config())

    text, markup = callback.message.answers[0]
    assert text == "Web 1"
    assert markup == server_menu_keyboard("web1")
    assert callback.answers == [(None, False)]


async def test_cb_menu_unknown_server_alerts():
    from bot.handlers import servers as servers_module

    callback = FakeCallback("menu:missing")
    await servers_module.cb_menu(callback, make_config())

    assert callback.message.answers == []
    assert callback.answers == [("Сервер не найден", True)]
