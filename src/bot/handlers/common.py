from __future__ import annotations

import html

from aiogram import BaseMiddleware
from aiogram.fsm.state import State, StatesGroup

from bot.alerts.engine import AlertRuntime
from bot.config import AppConfig, ServerConfig
from bot.formatting import format_command_result
from bot.security import ConfirmationStore
from bot.ssh.pool import ServerUnavailable, SshPool


class ShellState(StatesGroup):
    waiting_command = State()


class MenuState(StatesGroup):
    units = State()
    docker = State()


class DependenciesMiddleware(BaseMiddleware):
    def __init__(
        self,
        config: AppConfig,
        pool: SshPool,
        confirmations: ConfirmationStore,
        runtime: AlertRuntime,
    ) -> None:
        self._config = config
        self._pool = pool
        self._confirmations = confirmations
        self._runtime = runtime

    async def __call__(self, handler, event, data):
        data["config"] = self._config
        data["pool"] = self._pool
        data["confirmations"] = self._confirmations
        data["runtime"] = self._runtime
        return await handler(event, data)


def parse_callback(data: str) -> tuple[str, str]:
    action, _, value = data.partition(":")
    return action, value


async def run_command(
    pool: SshPool,
    server: ServerConfig,
    command: str,
    max_lines: int,
    answer,
) -> None:
    try:
        result = await pool.run(server, command)
    except ServerUnavailable as exc:
        await answer(
            f"❌ {html.escape(server.name)}: недоступен ({html.escape(str(exc))})"
        )
        return
    await answer(format_command_result(result, max_lines))
