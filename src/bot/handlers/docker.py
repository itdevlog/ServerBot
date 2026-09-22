import functools

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.actions.base import InvalidArgument
from bot.actions.docker import docker_logs_command, docker_restart_action
from bot.collectors.docker import CollectorError, collect_docker
from bot.config import AppConfig
from bot.handlers.common import MenuState, run_command
from bot.keyboards import confirm_keyboard, docker_keyboard
from bot.security import ConfirmationStore
from bot.ssh.pool import ServerUnavailable, SshPool

router = Router()


@router.callback_query(F.data.startswith("docker:"))
async def cb_docker(
    callback: CallbackQuery, state: FSMContext, config: AppConfig, pool: SshPool
) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    try:
        containers = await collect_docker(pool, server)
    except (ServerUnavailable, CollectorError) as exc:
        await callback.answer(f"Ошибка: {exc}", show_alert=True)
        return
    names = [container.name for container in containers]
    if not names:
        await callback.message.answer("Контейнеров нет")
        await callback.answer()
        return
    await state.set_state(MenuState.docker)
    await state.update_data(server_id=server_id, containers=names)
    await callback.message.answer("Контейнеры:", reply_markup=docker_keyboard(names))
    await callback.answer()


@router.callback_query(F.data.startswith("dlog:"), MenuState.docker)
async def cb_dlog(
    callback: CallbackQuery, state: FSMContext, config: AppConfig, pool: SshPool
) -> None:
    index = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    names = data.get("containers", [])
    server = config.server(data.get("server_id", ""))
    if server is None or index >= len(names):
        await callback.answer("Список устарел", show_alert=True)
        return
    await run_command(
        pool,
        server,
        docker_logs_command(names[index]),
        config.defaults.output_max_lines,
        functools.partial(callback.message.answer, parse_mode="HTML"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("drestart:"), MenuState.docker)
async def cb_drestart(
    callback: CallbackQuery,
    state: FSMContext,
    config: AppConfig,
    confirmations: ConfirmationStore,
) -> None:
    index = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    names = data.get("containers", [])
    server = config.server(data.get("server_id", ""))
    if server is None or index >= len(names):
        await callback.answer("Список устарел", show_alert=True)
        return
    try:
        action = docker_restart_action(server, names[index])
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
