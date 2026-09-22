from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.alerts.engine import AlertRuntime
from bot.config import AppConfig

router = Router()


def alerts_text(config: AppConfig, runtime: AlertRuntime) -> str:
    thresholds = config.alerts.thresholds
    state = "включены" if runtime.enabled else "выключены"
    offline = "да" if thresholds.offline else "нет"
    return (
        f"Алерты: {state}\n"
        f"CPU > {thresholds.cpu_percent}%\n"
        f"RAM > {thresholds.ram_percent}%\n"
        f"Диск > {thresholds.disk_percent}%\n"
        f"Load/CPU > {thresholds.load_per_cpu}\n"
        f"Offline: {offline}\n"
        f"Интервал: {config.alerts.interval}с, cooldown: {config.alerts.cooldown}с"
    )


def alerts_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    label = "🔕 Выключить" if enabled else "🔔 Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data="alerts:toggle")]
        ]
    )


@router.message(Command("alerts"))
async def cmd_alerts(
    message: Message, config: AppConfig, runtime: AlertRuntime
) -> None:
    await message.answer(
        alerts_text(config, runtime), reply_markup=alerts_keyboard(runtime.enabled)
    )


@router.callback_query(F.data == "alerts:toggle")
async def cb_alerts(
    callback: CallbackQuery, config: AppConfig, runtime: AlertRuntime
) -> None:
    runtime.enabled = not runtime.enabled
    await callback.message.edit_text(
        alerts_text(config, runtime), reply_markup=alerts_keyboard(runtime.enabled)
    )
    await callback.answer()
