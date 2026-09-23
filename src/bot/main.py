from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.alerts.engine import AlertEngine, AlertEvent, AlertRuntime
from bot.collectors.system import CollectorError, collect_system
from bot.config import AppConfig, load_config
from bot.env import load_env_file
from bot.formatting import format_alert
from bot.handlers import (
    alerts,
    confirm,
    docker,
    services,
    shell,
    start,
    status,
    updates,
    servers,
)
from bot.handlers.common import DependenciesMiddleware
from bot.security import ConfirmationStore, WhitelistMiddleware
from bot.ssh.pool import ServerUnavailable, SshPool

logger = logging.getLogger(__name__)


def build_dispatcher(
    config: AppConfig,
    pool: SshPool,
    confirmations: ConfirmationStore,
    runtime: AlertRuntime,
) -> Dispatcher:
    dispatcher = Dispatcher()
    whitelist = WhitelistMiddleware(config.telegram.allowed_users)
    dispatcher.message.middleware(whitelist)
    dispatcher.callback_query.middleware(whitelist)

    dependencies = DependenciesMiddleware(config, pool, confirmations, runtime)
    dispatcher.message.middleware(dependencies)
    dispatcher.callback_query.middleware(dependencies)

    for module in (
        start,
        servers,
        status,
        services,
        updates,
        docker,
        shell,
        alerts,
        confirm,
    ):
        dispatcher.include_router(module.router)
    return dispatcher


async def _poll_server(
    pool: SshPool, server, engine: AlertEngine
) -> list[AlertEvent]:
    try:
        metrics = await collect_system(pool, server)
    except ServerUnavailable as exc:
        logger.warning("Poll failed for %s: %s", server.id, exc)
        return engine.record_failure(server.id)
    except CollectorError as exc:
        logger.warning("Metrics parse failed for %s: %s", server.id, exc)
        return engine.mark_online(server.id)
    return engine.mark_online(server.id) + engine.evaluate(server.id, metrics)


async def poll_and_alert(
    bot: Bot,
    config: AppConfig,
    pool: SshPool,
    engine: AlertEngine,
    runtime: AlertRuntime,
) -> None:
    if not runtime.enabled:
        return
    results = await asyncio.gather(
        *(_poll_server(pool, server, engine) for server in config.servers),
        return_exceptions=True,
    )
    for server, result in zip(config.servers, results):
        if isinstance(result, BaseException):
            logger.warning("Poll task failed for %s: %s", server.id, result)
            continue
        for event in result:
            message = format_alert(event, server)
            for user_id in config.telegram.allowed_users:
                try:
                    await bot.send_message(user_id, message, parse_mode="HTML")
                except Exception as exc:
                    logger.warning("Failed to send alert to %s: %s", user_id, exc)


async def run(config: AppConfig) -> None:
    bot = Bot(config.telegram.token)
    pool = SshPool(config.defaults.ssh)
    confirmations = ConfirmationStore(ttl=60.0)
    runtime = AlertRuntime(enabled=config.alerts.enabled)
    engine = AlertEngine(config.alerts.thresholds, config.alerts.cooldown)
    dispatcher = build_dispatcher(config, pool, confirmations, runtime)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_and_alert,
        "interval",
        seconds=config.alerts.interval,
        args=[bot, config, pool, engine, runtime],
    )
    scheduler.start()
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await pool.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    load_env_file()
    config = load_config("config.yaml")
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
