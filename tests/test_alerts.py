from bot.alerts.engine import AlertEngine
from bot.collectors.system import SystemMetrics
from bot.config import Thresholds


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def metrics(cpu=10.0, ram=10.0, disk=10.0, load=0.1, cores=2) -> SystemMetrics:
    return SystemMetrics("h", cpu, ram, disk, load, load, load, cores, 1.0)


def make_engine(clock=None, cooldown=300.0) -> AlertEngine:
    return AlertEngine(
        Thresholds(cpu_percent=85, ram_percent=90, disk_percent=85, load_per_cpu=2.0),
        cooldown,
        clock or FakeClock(),
    )


def test_healthy_metrics_emit_nothing():
    assert make_engine().evaluate("web1", metrics()) == []


def test_cpu_breach_emits_enter():
    events = make_engine().evaluate("web1", metrics(cpu=95))

    assert len(events) == 1
    assert events[0].problem == "cpu"
    assert events[0].kind == "enter"


def test_persisting_breach_does_not_repeat():
    engine = make_engine()
    engine.evaluate("web1", metrics(cpu=95))

    assert engine.evaluate("web1", metrics(cpu=96)) == []


def test_recovery_emits_resolve():
    clock = FakeClock()
    engine = make_engine(clock=clock, cooldown=300)
    clock.now = 1000
    engine.evaluate("web1", metrics(cpu=95))
    clock.now = 1400
    events = engine.evaluate("web1", metrics(cpu=10))

    assert len(events) == 1
    assert events[0].problem == "cpu"
    assert events[0].kind == "resolve"


def test_ram_and_disk_and_load_breaches():
    events = make_engine().evaluate(
        "web1", metrics(cpu=10, ram=95, disk=90, load=5.0, cores=2)
    )

    assert sorted(e.problem for e in events) == ["disk", "load", "ram"]


def test_cooldown_suppresses_reentry_then_allows():
    clock = FakeClock()
    engine = make_engine(clock=clock, cooldown=300)
    engine.evaluate("web1", metrics(cpu=95))
    clock.now = 10
    engine.evaluate("web1", metrics(cpu=10))
    clock.now = 20
    assert engine.evaluate("web1", metrics(cpu=95)) == []
    clock.now = 310
    events = engine.evaluate("web1", metrics(cpu=95))
    assert [e.kind for e in events] == ["enter"]


def test_resolve_repeats_are_suppressed_by_cooldown():
    clock = FakeClock()
    engine = make_engine(clock=clock, cooldown=300)
    clock.now = 1000
    engine.evaluate("web1", metrics(cpu=95))
    clock.now = 1400
    assert [e.kind for e in engine.evaluate("web1", metrics(cpu=10))] == ["resolve"]

    clock.now = 1500
    engine.evaluate("web1", metrics(cpu=95))
    clock.now = 1600
    assert engine.evaluate("web1", metrics(cpu=10)) == []

    clock.now = 1800
    engine.evaluate("web1", metrics(cpu=95))
    clock.now = 2100
    events = engine.evaluate("web1", metrics(cpu=10))
    assert [e.kind for e in events] == ["resolve"]


def test_offline_alert_only_after_threshold_failures():
    engine = make_engine()

    assert engine.record_failure("web1") == []
    assert engine.record_failure("web1") == []
    events = engine.record_failure("web1")

    assert [e.problem for e in events] == ["offline"]
    assert events[0].kind == "enter"


def test_mark_online_resets_failure_streak():
    engine = make_engine()
    engine.record_failure("web1")
    engine.record_failure("web1")

    assert engine.mark_online("web1") == []

    assert engine.record_failure("web1") == []
    assert engine.record_failure("web1") == []
    events = engine.record_failure("web1")
    assert [e.problem for e in events] == ["offline"]


def test_offline_resolve_after_enter():
    clock = FakeClock()
    engine = make_engine(clock=clock, cooldown=300)
    engine.record_failure("web1")
    engine.record_failure("web1")
    engine.record_failure("web1")

    clock.now = 1000
    events = engine.mark_online("web1")

    assert [e.problem for e in events] == ["offline"]
    assert events[0].kind == "resolve"


def test_offline_disabled_returns_empty():
    engine = AlertEngine(Thresholds(offline=False), 300.0, FakeClock())

    assert engine.record_failure("web1") == []
    assert engine.record_failure("web1") == []
    assert engine.record_failure("web1") == []


def test_mark_online_preserves_metric_problems():
    clock = FakeClock()
    engine = make_engine(clock=clock, cooldown=300)
    assert [e.problem for e in engine.evaluate("web1", metrics(cpu=95))] == ["cpu"]

    clock.now = 30
    assert engine.mark_online("web1") == []
    assert engine.evaluate("web1", metrics(cpu=96)) == []
    assert engine._active["web1"] == {"cpu"}


def test_sustained_breach_never_resolves_across_mark_online_ticks():
    clock = FakeClock()
    engine = make_engine(clock=clock, cooldown=300)
    engine.evaluate("web1", metrics(cpu=95))

    for tick in range(1, 5):
        clock.now = tick * 60
        assert engine.mark_online("web1") == []
        events = engine.evaluate("web1", metrics(cpu=96))
        assert [e.kind for e in events] == []


def test_mark_online_without_offline_returns_empty():
    engine = make_engine()

    assert engine.mark_online("web1") == []
