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

    async def answer(self, text, reply_markup=None, **kwargs) -> None:
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


class FakeState:
    def __init__(self, data) -> None:
        self._data = data
        self.cleared = False

    async def get_data(self):
        return self._data

    async def clear(self) -> None:
        self.cleared = True


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class FakePool:
    def __init__(self) -> None:
        self.commands: list[str] = []

    async def run(self, server, command, timeout=None):
        from bot.ssh.pool import CommandResult

        self.commands.append(command)
        return CommandResult("done", "", 0, 0.1)


async def test_unit_start_runs_without_confirmation():
    from bot.handlers import services as services_module
    from bot.security import ConfirmationStore

    callback = FakeCallback("unitact:start:0")
    callback.from_user = FakeUser(1)
    state = FakeState({"server_id": "web1", "units": ["nginx"]})
    pool = FakePool()
    confirmations = ConfirmationStore()

    await services_module.cb_unitact(
        callback, state, make_config(), confirmations, pool
    )

    assert pool.commands == ["systemctl start nginx"]
    assert confirmations.pending_count() == 0


async def test_unit_restart_requires_confirmation():
    from bot.handlers import services as services_module
    from bot.security import ConfirmationStore

    callback = FakeCallback("unitact:restart:0")
    callback.from_user = FakeUser(1)
    state = FakeState({"server_id": "web1", "units": ["nginx"]})
    pool = FakePool()
    confirmations = ConfirmationStore()

    await services_module.cb_unitact(
        callback, state, make_config(), confirmations, pool
    )

    assert pool.commands == []
    assert confirmations.pending_count() == 1


async def test_shell_empty_command_is_rejected():
    from bot.handlers import shell as shell_module
    from bot.security import ConfirmationStore

    message = FakeMessage()
    message.text = "   "
    state = FakeState({"server_id": "web1"})
    confirmations = ConfirmationStore()

    await shell_module.on_shell_command(message, state, make_config(), confirmations)

    assert state.cleared is True
    assert message.answers
    assert confirmations.pending_count() == 0
