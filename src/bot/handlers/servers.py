from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.collectors.system import CollectorError, collect_system
from bot.config import AppConfig
from bot.keyboards import servers_keyboard
from bot.ssh.pool import ServerUnavailable, SshPool

router = Router()


@router.message(Command("servers"))
async def cmd_servers(message: Message, config: AppConfig) -> None:
    await message.answer("Серверы:", reply_markup=servers_keyboard(config.servers))


@router.message(Command("statusall"))
async def cmd_statusall(message: Message, config: AppConfig, pool: SshPool) -> None:
    lines = []
    for server in config.servers:
        try:
            metrics = await collect_system(pool, server)
        except (ServerUnavailable, CollectorError) as exc:
            lines.append(f"🔴 {server.name}: недоступен ({exc})")
            continue
        lines.append(
            f"🟢 {server.name}: CPU {metrics.cpu_percent:.0f}% "
            f"RAM {metrics.ram_percent:.0f}% Диск {metrics.disk_percent:.0f}%"
        )
    await message.answer("\n".join(lines))
