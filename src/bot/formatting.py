from __future__ import annotations

import html

from bot.alerts.engine import AlertEvent
from bot.collectors.system import SystemMetrics
from bot.config import ServerConfig
from bot.ssh.pool import CommandResult


def truncate_output(text: str, max_lines: int) -> str:
    lines = text.rstrip("\n").splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    shown = lines[:max_lines]
    return "\n".join(shown) + f"\n… усечено ({len(lines) - max_lines} строк)"


def format_duration(seconds: float) -> str:
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    parts.append(f"{minutes}м")
    return " ".join(parts)


def format_metrics(server: ServerConfig, metrics: SystemMetrics) -> str:
    name = html.escape(server.name)
    host = html.escape(server.host)
    hostname = html.escape(metrics.hostname)
    return (
        f"📊 <b>{name}</b> ({host})\n"
        f"hostname: {hostname}\n"
        f"CPU: {metrics.cpu_percent:.1f}% (ядер: {metrics.cpu_count})\n"
        f"RAM: {metrics.ram_percent:.1f}%\n"
        f"Диск /: {metrics.disk_percent:.0f}%\n"
        f"Load: {metrics.load1:.2f} {metrics.load5:.2f} {metrics.load15:.2f}\n"
        f"Uptime: {format_duration(metrics.uptime_seconds)}"
    )


def format_alert(event: AlertEvent, server: ServerConfig) -> str:
    name = html.escape(server.name)
    if event.kind == "resolve":
        return f"🟢 <b>{name}</b>: {event.problem} в норме"
    if event.problem == "offline":
        return f"🔴 <b>{name}</b>: сервер недоступен"
    return f"🟠 <b>{name}</b>: {html.escape(event.detail)}"


def confirm_prompt(template: str, server: ServerConfig, command: str) -> str:
    header = template.format(name=f"<b>{html.escape(server.name)}</b>")
    return f"{header}\n<code>{html.escape(command)}</code>"


def format_command_result(result: CommandResult, max_lines: int) -> str:
    body = result.stdout or result.stderr or "(пустой вывод)"
    escaped = html.escape(body)
    return (
        truncate_output(escaped, max_lines)
        + f"\n\nкод: {result.exit_status}, {result.duration:.1f}с"
    )
