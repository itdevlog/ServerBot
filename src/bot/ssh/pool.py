from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

import asyncssh

from bot.config import ServerConfig, SshDefaults


class ServerUnavailable(Exception):
    pass


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_status: int
    duration: float


class SshPool:
    def __init__(self, defaults: SshDefaults) -> None:
        self._defaults = defaults
        self._connections: dict[str, asyncssh.SSHClientConnection] = {}
        self._semaphore = asyncio.Semaphore(defaults.max_concurrency)

    async def _connect(self, server: ServerConfig):
        kwargs = {
            "host": server.host,
            "port": server.port,
            "username": server.user,
            "known_hosts": None,
            "connect_timeout": self._defaults.connect_timeout,
        }
        if server.auth.type == "password":
            kwargs["password"] = server.auth.password
        else:
            kwargs["client_keys"] = [os.path.expanduser(server.auth.key_path or "")]
            if server.auth.passphrase:
                kwargs["passphrase"] = server.auth.passphrase
        return await asyncssh.connect(**kwargs)

    async def _get_connection(self, server: ServerConfig):
        connection = self._connections.get(server.id)
        if connection is not None:
            return connection
        connection = await self._connect(server)
        self._connections[server.id] = connection
        return connection

    async def run(
        self, server: ServerConfig, command: str, timeout: float | None = None
    ) -> CommandResult:
        limit = timeout if timeout is not None else self._defaults.command_timeout
        async with self._semaphore:
            started = time.monotonic()
            try:
                connection = await self._get_connection(server)
                result = await asyncio.wait_for(connection.run(command, check=False), limit)
            except (asyncssh.Error, OSError, asyncio.TimeoutError) as exc:
                connection = self._connections.pop(server.id, None)
                if connection is not None:
                    connection.close()
                raise ServerUnavailable(str(exc)) from exc
            duration = time.monotonic() - started
        return CommandResult(
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            exit_status=result.exit_status or 0,
            duration=duration,
        )

    async def aclose(self) -> None:
        connections = list(self._connections.values())
        self._connections.clear()
        for connection in connections:
            connection.close()
            await connection.wait_closed()
