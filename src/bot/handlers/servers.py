import asyncio
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.collectors.system import collect_system
from bot.config import AppConfig
from bot.keyboards import server_menu_keyboard, servers_keyboard
from bot.ssh.pool import SshPool

router = Router()


@router.message(Command("servers"))
async def cmd_servers(message: Message, config: AppConfig) -> None:
    await message.answer("Серверы:", reply_markup=servers_keyboard(config.servers))


@router.message(Command("statusall"))
async def cmd_statusall(message: Message, config: AppConfig, pool: SshPool) -> None:
    results = await asyncio.gather(
        *(collect_system(pool, server) for server in config.servers),
        return_exceptions=True,
    )
    lines = []
    for server, result in zip(config.servers, results):
        if isinstance(result, BaseException):
            lines.append(f"🔴 {server.name}: недоступен ({result})")
            continue
        lines.append(
            f"🟢 {server.name}: CPU {result.cpu_percent:.0f}% "
            f"RAM {result.ram_percent:.0f}% Диск {result.disk_percent:.0f}%"
        )
    await message.answer("\n".join(lines))


@router.callback_query(F.data.startswith("menu:"))
async def cb_menu(callback: CallbackQuery, config: AppConfig) -> None:
    server = config.server(callback.data.split(":", 1)[1])
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    await callback.message.answer(
        server.name, reply_markup=server_menu_keyboard(server.id)
    )
    await callback.answer()
