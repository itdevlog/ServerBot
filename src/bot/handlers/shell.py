from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.actions.shell import shell_action
from bot.config import AppConfig
from bot.handlers.common import ShellState
from bot.keyboards import confirm_keyboard
from bot.security import ConfirmationStore

router = Router()


async def start_shell(
    message: Message, state: FSMContext, config: AppConfig, server_id: str
) -> None:
    if not server_id:
        await message.answer("Использование: /shell <server_id>")
        return
    server = config.server(server_id.strip())
    if server is None:
        await message.answer("Сервер не найден")
        return
    await state.set_state(ShellState.waiting_command)
    await state.update_data(server_id=server.id)
    await message.answer(f"Введи команду для {server.name}:")


@router.message(Command("shell"))
async def cmd_shell(message: Message, state: FSMContext, config: AppConfig) -> None:
    parts = (message.text or "").split(maxsplit=1)
    server_id = parts[1] if len(parts) > 1 else ""
    await start_shell(message, state, config, server_id)


@router.callback_query(F.data.startswith("shell:"))
async def cb_shell(callback: CallbackQuery, state: FSMContext, config: AppConfig) -> None:
    server_id = callback.data.split(":", 1)[1]
    await start_shell(callback.message, state, config, server_id)
    await callback.answer()


@router.message(ShellState.waiting_command)
async def on_shell_command(
    message: Message,
    state: FSMContext,
    config: AppConfig,
    confirmations: ConfirmationStore,
) -> None:
    data = await state.get_data()
    server = config.server(data.get("server_id", ""))
    if server is None:
        await message.answer("Сервер не найден")
        await state.clear()
        return
    action = shell_action(server, message.text or "")
    token = confirmations.create(message.from_user.id, action)
    await message.answer(
        f"Выполнить на <b>{server.name}</b>:\n<code>{html.escape(action.command)}</code>",
        reply_markup=confirm_keyboard(token),
        parse_mode="HTML",
    )
    await state.clear()
