from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass
from typing import Iterable

from aiogram import BaseMiddleware

from bot.actions.base import PreparedAction

logger = logging.getLogger(__name__)


@dataclass
class PendingAction:
    user_id: int
    action: PreparedAction
    expires_at: float


class ConfirmationStore:
    def __init__(self, ttl: float = 60.0, clock=time.monotonic) -> None:
        self._ttl = ttl
        self._clock = clock
        self._pending: dict[str, PendingAction] = {}

    def create(self, user_id: int, action: PreparedAction) -> str:
        token = secrets.token_hex(4)
        self._pending[token] = PendingAction(
            user_id=user_id,
            action=action,
            expires_at=self._clock() + self._ttl,
        )
        return token

    def take(self, user_id: int, token: str) -> PreparedAction | None:
        item = self._pending.pop(token, None)
        if item is None:
            return None
        if item.user_id != user_id:
            return None
        if item.expires_at < self._clock():
            return None
        return item.action


class WhitelistMiddleware(BaseMiddleware):
    def __init__(self, allowed_users: Iterable[int]) -> None:
        self._allowed = set(allowed_users)

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None or user.id not in self._allowed:
            logger.warning("Blocked access attempt from user %s", getattr(user, "id", None))
            return None
        return await handler(event, data)
