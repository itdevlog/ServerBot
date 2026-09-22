from __future__ import annotations

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import ServerConfig


def servers_keyboard(servers: Sequence[ServerConfig]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=server.name, callback_data=f"menu:{server.id}")]
        for server in servers
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def server_menu_keyboard(server_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Метрики", callback_data=f"metrics:{server_id}")],
            [InlineKeyboardButton(text="⚙️ Сервисы", callback_data=f"units:{server_id}")],
            [InlineKeyboardButton(text="📦 Обновления", callback_data=f"updates:{server_id}")],
            [InlineKeyboardButton(text="🐳 Docker", callback_data=f"docker:{server_id}")],
            [InlineKeyboardButton(text="💻 Shell", callback_data=f"shell:{server_id}")],
            [InlineKeyboardButton(text="🔄 Reboot", callback_data=f"reboot:{server_id}")],
        ]
    )


def units_keyboard(unit_names: Sequence[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"unit:{index}")]
        for index, name in enumerate(unit_names)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def unit_actions_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Restart", callback_data=f"unitact:restart:{index}"),
                InlineKeyboardButton(text="⏹ Stop", callback_data=f"unitact:stop:{index}"),
                InlineKeyboardButton(text="▶️ Start", callback_data=f"unitact:start:{index}"),
            ],
            [InlineKeyboardButton(text="📜 Логи", callback_data=f"unitlogs:{index}")],
        ]
    )


def docker_keyboard(container_names: Sequence[str]) -> InlineKeyboardMarkup:
    rows = []
    for index, name in enumerate(container_names):
        rows.append(
            [
                InlineKeyboardButton(text=f"📜 {name}", callback_data=f"dlog:{index}"),
                InlineKeyboardButton(text=f"🔄 {name}", callback_data=f"drestart:{index}"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{token}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel:{token}"),
            ]
        ]
    )
