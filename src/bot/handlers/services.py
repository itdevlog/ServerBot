import functools

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.actions.base import InvalidArgument
from bot.actions.services import (
    LIST_UNITS_COMMAND,
    logs_command,
    parse_systemctl_units,
    service_action,
)
from bot.config import AppConfig
from bot.handlers.common import MenuState, run_command
from bot.keyboards import confirm_keyboard, unit_actions_keyboard, units_keyboard
from bot.security import ConfirmationStore
from bot.ssh.pool import ServerUnavailable, SshPool

router = Router()


@router.callback_query(F.data.startswith("units:"))
async def cb_units(
    callback: CallbackQuery, state: FSMContext, config: AppConfig, pool: SshPool
) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    try:
        result = await pool.run(server, LIST_UNITS_COMMAND)
    except ServerUnavailable as exc:
        await callback.answer(f"Недоступен: {exc}", show_alert=True)
        return
    units = [unit.name for unit in parse_systemctl_units(result.stdout)]
    await state.set_state(MenuState.units)
    await state.update_data(server_id=server_id, units=units)
    await callback.message.answer("Выбери сервис:", reply_markup=units_keyboard(units))
    await callback.answer()


@router.callback_query(F.data.startswith("unit:"), MenuState.units)
async def cb_unit(callback: CallbackQuery, state: FSMContext) -> None:
    index = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    units = data.get("units", [])
    if index >= len(units):
        await callback.answer("Список устарел", show_alert=True)
        return
    await state.update_data(selected=index)
    await callback.message.answer(units[index], reply_markup=unit_actions_keyboard(index))
    await callback.answer()


@router.callback_query(F.data.startswith("unitact:"), MenuState.units)
async def cb_unitact(
    callback: CallbackQuery,
    state: FSMContext,
    config: AppConfig,
    confirmations: ConfirmationStore,
) -> None:
    parts = callback.data.split(":")
    verb, raw_index = parts[1], int(parts[2])
    data = await state.get_data()
    units = data.get("units", [])
    server = config.server(data.get("server_id", ""))
    if server is None or raw_index >= len(units):
        await callback.answer("Список устарел", show_alert=True)
        return
    try:
        action = service_action(server, units[raw_index], verb)
    except InvalidArgument as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    token = confirmations.create(callback.from_user.id, action)
    await callback.message.answer(
        f"Выполнить на <b>{server.name}</b>:\n<code>{action.command}</code>",
        reply_markup=confirm_keyboard(token),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("unitlogs:"), MenuState.units)
async def cb_unitlogs(
    callback: CallbackQuery, state: FSMContext, config: AppConfig, pool: SshPool
) -> None:
    index = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    units = data.get("units", [])
    server = config.server(data.get("server_id", ""))
    if server is None or index >= len(units):
        await callback.answer("Список устарел", show_alert=True)
        return
    await run_command(
        pool,
        server,
        logs_command(units[index]),
        config.defaults.output_max_lines,
        functools.partial(callback.message.answer, parse_mode="HTML"),
    )
    await callback.answer()
