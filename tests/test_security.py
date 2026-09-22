from bot.actions.base import PreparedAction
from bot.security import ConfirmationStore, WhitelistMiddleware


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


ACTION = PreparedAction("web1", "restart nginx", "systemctl restart nginx", True)


def test_confirmation_roundtrip():
    store = ConfirmationStore(clock=FakeClock())
    token = store.create(1, ACTION)

    assert store.take(1, token) is ACTION


def test_confirmation_is_single_use():
    store = ConfirmationStore(clock=FakeClock())
    token = store.create(1, ACTION)
    store.take(1, token)

    assert store.take(1, token) is None


def test_confirmation_rejects_wrong_user():
    store = ConfirmationStore(clock=FakeClock())
    token = store.create(1, ACTION)

    assert store.take(2, token) is None


def test_confirmation_expires():
    clock = FakeClock()
    store = ConfirmationStore(ttl=60.0, clock=clock)
    token = store.create(1, ACTION)
    clock.now = 61.0

    assert store.take(1, token) is None


def test_confirmation_unknown_token():
    store = ConfirmationStore(clock=FakeClock())

    assert store.take(1, "nope") is None


async def test_whitelist_blocks_unknown_user():
    middleware = WhitelistMiddleware([1])
    called = False

    async def handler(event, data):
        nonlocal called
        called = True
        return "ok"

    result = await middleware(handler, None, {"event_from_user": FakeUser(2)})

    assert result is None
    assert called is False


async def test_whitelist_allows_known_user():
    middleware = WhitelistMiddleware([1])

    async def handler(event, data):
        return "ok"

    result = await middleware(handler, None, {"event_from_user": FakeUser(1)})

    assert result == "ok"


async def test_whitelist_blocks_missing_user():
    middleware = WhitelistMiddleware([1])

    async def handler(event, data):
        return "ok"

    assert await middleware(handler, None, {}) is None
