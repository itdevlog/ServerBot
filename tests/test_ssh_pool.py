import asyncio
import os
import shutil
import subprocess

import asyncssh
import pytest

from bot.config import ServerConfig, SshDefaults
from bot.ssh.pool import CommandResult, ServerUnavailable, SshPool


def make_server(server_id: str = "web1") -> ServerConfig:
    return ServerConfig(
        id=server_id,
        name="Web 1",
        host="1.2.3.4",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


class FakeResult:
    def __init__(self, stdout: str, stderr: str, exit_status: int):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_status = exit_status


class FakeConn:
    def __init__(self):
        self.closed = False
        self.commands: list[str] = []

    async def run(self, command: str, check: bool = False) -> FakeResult:
        self.commands.append(command)
        return FakeResult("ok", "", 0)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


async def test_run_returns_command_result(monkeypatch):
    conn = FakeConn()

    async def fake_connect(**kwargs):
        return conn

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())
    result = await pool.run(make_server(), "echo ok")

    assert result == CommandResult("ok", "", 0, result.duration)
    assert result.exit_status == 0
    assert conn.commands == ["echo ok"]


async def test_connection_is_cached(monkeypatch):
    conn = FakeConn()
    calls = 0

    async def fake_connect(**kwargs):
        nonlocal calls
        calls += 1
        return conn

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())
    await pool.run(make_server(), "a")
    await pool.run(make_server(), "b")

    assert calls == 1


async def test_connection_error_raises_server_unavailable(monkeypatch):
    async def fake_connect(**kwargs):
        raise OSError("boom")

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())

    with pytest.raises(ServerUnavailable, match="boom"):
        await pool.run(make_server(), "x")


async def test_password_auth_passes_password(monkeypatch):
    captured = {}

    async def fake_connect(**kwargs):
        captured.update(kwargs)
        return FakeConn()

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())
    await pool.run(make_server(), "x")

    assert captured["password"] == "secret"
    assert captured["host"] == "1.2.3.4"
    assert captured["username"] == "admin"


async def test_key_auth_passes_client_keys(monkeypatch):
    captured = {}

    async def fake_connect(**kwargs):
        captured.update(kwargs)
        return FakeConn()

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())
    server = ServerConfig(
        id="db1",
        name="DB 1",
        host="5.6.7.8",
        user="deploy",
        auth={"type": "key", "key_path": "~/.ssh/db1", "passphrase": "k"},
    )
    await pool.run(server, "x")

    assert captured["client_keys"] == [os.path.expanduser("~/.ssh/db1")]
    assert captured["passphrase"] == "k"


async def test_evicted_connection_is_closed_on_command_failure(monkeypatch):
    conn = FakeConn()

    async def failing_run(command: str, check: bool = False):
        raise OSError("command failed")

    conn.run = failing_run

    async def fake_connect(**kwargs):
        return conn

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())

    with pytest.raises(ServerUnavailable, match="command failed"):
        await pool.run(make_server(), "x")

    assert conn.closed is True
    assert make_server().id not in pool._connections


async def test_aclose_closes_cached_connections(monkeypatch):
    conn = FakeConn()

    async def fake_connect(**kwargs):
        return conn

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults())
    await pool.run(make_server(), "x")
    await pool.aclose()

    assert conn.closed is True


def test_encrypted_openssh_key_loads(tmp_path):
    if shutil.which("ssh-keygen") is None:
        pytest.skip("ssh-keygen not available")

    key_path = tmp_path / "id_ed25519"
    passphrase = "secret123"
    subprocess.run(
        [
            "ssh-keygen",
            "-t",
            "ed25519",
            "-N",
            passphrase,
            "-f",
            str(key_path),
            "-q",
        ],
        check=True,
    )

    key = asyncssh.import_private_key(key_path.read_text(), passphrase)

    assert key is not None


async def test_run_respects_max_concurrency(monkeypatch):
    active = 0
    peak = 0

    class SlowConn(FakeConn):
        async def run(self, command: str, check: bool = False) -> FakeResult:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return FakeResult("ok", "", 0)

    conn = SlowConn()

    async def fake_connect(**kwargs):
        return conn

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    pool = SshPool(SshDefaults(max_concurrency=2))
    servers = [make_server(f"s{i}") for i in range(6)]

    await asyncio.gather(*(pool.run(server, "x") for server in servers))

    assert peak <= 2
