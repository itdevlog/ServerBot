from __future__ import annotations

import time
from dataclasses import dataclass

from bot.collectors.system import SystemMetrics
from bot.config import Thresholds


@dataclass(frozen=True)
class AlertEvent:
    server_id: str
    problem: str
    kind: str
    detail: str


@dataclass
class AlertRuntime:
    enabled: bool = True


class AlertEngine:
    def __init__(
        self, thresholds: Thresholds, cooldown: float, clock=time.monotonic
    ) -> None:
        self._thresholds = thresholds
        self._cooldown = cooldown
        self._clock = clock
        self._active: dict[str, set[str]] = {}
        self._last_sent: dict[tuple[str, str], float] = {}

    def _transition(
        self, server_id: str, problems: dict[str, str], now: float
    ) -> list[AlertEvent]:
        previous = self._active.get(server_id, set())
        current = set(problems)
        new_active = set(previous)
        events: list[AlertEvent] = []

        for name in sorted(current - previous):
            key = (server_id, name)
            last = self._last_sent.get(key)
            if last is None or now - last >= self._cooldown:
                self._last_sent[key] = now
                new_active.add(name)
                events.append(AlertEvent(server_id, name, "enter", problems[name]))

        for name in sorted(previous - current):
            new_active.discard(name)
            events.append(AlertEvent(server_id, name, "resolve", ""))

        self._active[server_id] = new_active
        return events

    def evaluate(self, server_id: str, metrics: SystemMetrics) -> list[AlertEvent]:
        problems: dict[str, str] = {}
        if metrics.cpu_percent > self._thresholds.cpu_percent:
            problems["cpu"] = f"CPU {metrics.cpu_percent:.0f}%"
        if metrics.ram_percent > self._thresholds.ram_percent:
            problems["ram"] = f"RAM {metrics.ram_percent:.0f}%"
        if metrics.disk_percent > self._thresholds.disk_percent:
            problems["disk"] = f"диск {metrics.disk_percent:.0f}%"
        if metrics.load_per_cpu > self._thresholds.load_per_cpu:
            problems["load"] = f"load {metrics.load_per_cpu:.2f}/CPU"
        return self._transition(server_id, problems, self._clock())

    def evaluate_offline(self, server_id: str) -> list[AlertEvent]:
        if not self._thresholds.offline:
            return []
        return self._transition(
            server_id, {"offline": "сервер недоступен"}, self._clock()
        )

    def mark_online(self, server_id: str) -> list[AlertEvent]:
        previous = self._active.get(server_id, set())
        if "offline" not in previous:
            return []
        new_active = set(previous)
        new_active.discard("offline")
        self._active[server_id] = new_active
        return [AlertEvent(server_id, "offline", "resolve", "")]
