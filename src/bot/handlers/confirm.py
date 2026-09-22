import functools

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.config import AppConfig
from bot.handlers.common import run_command
from bot.security import ConfirmationStore
from bot.ssh.pool import SshPool

router = Router()


@router.callback_query(F.data.startswith("confirm:"))
async def cb_confirm(
    callback: CallbackQuery,
    config: AppConfig,
    pool: SshPool,
    confirmations: ConfirmationStore,
) -> None:
    token = callback.data.split(":", 1)[1]
    action = confirmations.take(callback.from_user.id, token)
    if action is None:
        await callback.answer("Подтверждение истекло или недействительно", show_alert=True)
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    server = config.server(action.server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    await callback.answer("Выполняю…")
    await run_command(
        pool,
        server,
        action.command,
        config.defaults.output_max_lines,
        functools.partial(callback.message.answer, parse_mode="HTML"),
    )


@router.callback_query(F.data.startswith("cancel:"))
async def cb_cancel(callback: CallbackQuery, confirmations: ConfirmationStore) -> None:
    token = callback.data.split(":", 1)[1]
    confirmations.take(callback.from_user.id, token)
    await callback.message.edit_text("❌ Отменено")
    await callback.answer()
