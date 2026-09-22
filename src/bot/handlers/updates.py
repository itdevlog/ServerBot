from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.actions.updates import (
    UPGRADABLE_COMMAND,
    parse_upgradable,
    reboot_action,
    upgrade_action,
)
from bot.config import AppConfig
from bot.formatting import confirm_prompt
from bot.keyboards import confirm_keyboard
from bot.security import ConfirmationStore
from bot.ssh.pool import ServerUnavailable, SshPool

router = Router()


@router.callback_query(F.data.startswith("updates:"))
async def cb_updates(callback: CallbackQuery, config: AppConfig, pool: SshPool) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    try:
        result = await pool.run(server, UPGRADABLE_COMMAND)
    except ServerUnavailable as exc:
        await callback.answer(f"Недоступен: {exc}", show_alert=True)
        return
    packages = parse_upgradable(result.stdout)
    if not packages:
        await callback.message.answer("Обновлений нет")
        await callback.answer()
        return
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Обновить", callback_data=f"upgrade:{server_id}")]
        ]
    )
    text = "Доступны обновления:\n" + "\n".join(f"• {name}" for name in packages)
    await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("upgrade:"))
async def cb_upgrade(
    callback: CallbackQuery, config: AppConfig, confirmations: ConfirmationStore
) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    action = upgrade_action(server)
    token = confirmations.create(callback.from_user.id, action)
    await callback.message.answer(
        confirm_prompt("Обновить пакеты на {name}?", server, action.command),
        reply_markup=confirm_keyboard(token),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reboot:"))
async def cb_reboot(
    callback: CallbackQuery, config: AppConfig, confirmations: ConfirmationStore
) -> None:
    server_id = callback.data.split(":", 1)[1]
    server = config.server(server_id)
    if server is None:
        await callback.answer("Сервер не найден", show_alert=True)
        return
    action = reboot_action(server)
    token = confirmations.create(callback.from_user.id, action)
    await callback.message.answer(
        confirm_prompt("Перезагрузить {name}?", server, action.command),
        reply_markup=confirm_keyboard(token),
        parse_mode="HTML",
    )
    await callback.answer()
