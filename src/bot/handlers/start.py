from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

HELP_TEXT = (
    "<b>VPS Manager</b>\n\n"
    "/servers — список серверов\n"
    "/statusall — сводка по всем серверам\n"
    "/status &lt;id&gt; — метрики сервера\n"
    "/shell &lt;id&gt; — выполнить команду\n"
    "/alerts — состояние уведомлений"
)


@router.message(Command("start", "help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")
