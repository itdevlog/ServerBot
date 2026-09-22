from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.collectors.system import CollectorError, collect_system
from bot.config import AppConfig, ServerConfig
from bot.formatting import format_metrics
from bot.ssh.pool import ServerUnavailable, SshPool

router = Router()


async def send_metrics(
    answer, pool: SshPool, server: ServerConfig
) -> None:
    try:
        metrics = await collect_system(pool, server)
    except (ServerUnavailable, CollectorError) as exc:
        await answer(f"❌ {server.name}: недоступен ({exc})")
        return
    await answer(format_metrics(server, metrics), parse_mode="HTML")


@router.message(Command("status"))
async def cmd_status(message: Message, config: AppConfig, pool: SshPool) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /status <server_id>")
        return
    server = config.server(parts[1].strip())
    if server is None:
        await message.answer("Сервер не найден")
        return
    await send_metrics(message.answer, pool, server)


@router.callback_query(F.data.startswith("metrics:"))
async def cb_metrics(callback: CallbackQuery, config: AppConfig, pool: SshPool) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    await send_metrics(callback.message.answer, pool, server)
    await callback.answer()
