from bot.alerts.engine import AlertEvent
from bot.collectors.system import SystemMetrics
from bot.config import ServerConfig
from bot.formatting import (
    confirm_prompt,
    format_alert,
    format_command_result,
    format_duration,
    format_metrics,
    probe_error_text,
    truncate_output,
)
from bot.ssh.pool import CommandResult


def make_server() -> ServerConfig:
    return ServerConfig(
        id="web1",
        name="Web 1",
        host="1.2.3.4",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


def make_unsafe_server() -> ServerConfig:
    return ServerConfig(
        id="x",
        name="A<B>&C",
        host="h<1>",
        user="admin",
        auth={"type": "password", "password": "secret"},
    )


def make_metrics() -> SystemMetrics:
    return SystemMetrics("vps-web1", 12.5, 40.0, 53.0, 0.5, 0.4, 0.3, 4, 90061.0)


def test_truncate_output_keeps_short_text():
    assert truncate_output("a\nb", 10) == "a\nb"


def test_truncate_output_cuts_long_text():
    text = "\n".join(str(i) for i in range(50))
    result = truncate_output(text, 10)

    assert result.startswith("0\n1\n")
    assert "усечено" in result


def test_format_duration():
    assert format_duration(90061) == "1д 1ч 1м"


def test_format_metrics_contains_fields():
    text = format_metrics(make_server(), make_metrics())

    assert "Web 1" in text
    assert "12.5%" in text
    assert "40.0%" in text
    assert "53%" in text
    assert "1д 1ч 1м" in text


def test_format_alert_enter_uses_detail():
    event = AlertEvent("web1", "cpu", "enter", "CPU 95%")
    text = format_alert(event, make_server())

    assert "Web 1" in text
    assert "CPU 95%" in text


def test_format_alert_offline():
    event = AlertEvent("web1", "offline", "enter", "сервер недоступен")
    text = format_alert(event, make_server())

    assert "недоступен" in text


def test_format_alert_resolve():
    event = AlertEvent("web1", "cpu", "resolve", "")
    text = format_alert(event, make_server())

    assert "норм" in text


def test_format_command_result_escapes_and_truncates():
    result = CommandResult("a\nb\nc", "", 0, 0.4)
    text = format_command_result(result, 2)

    assert "a" in text
    assert "код: 0" in text
    assert "усечено" in text


def test_format_metrics_escapes_config_values():
    metrics = SystemMetrics("<host>", 1.0, 2.0, 3.0, 0.1, 0.1, 0.1, 2, 10.0)
    text = format_metrics(make_unsafe_server(), metrics)

    assert "A&lt;B&gt;&amp;C" in text
    assert "h&lt;1&gt;" in text
    assert "&lt;host&gt;" in text
    assert "<B>" not in text


def test_format_alert_escapes_detail():
    event = AlertEvent("web1", "cpu", "enter", "CPU <b>95%</b>")
    text = format_alert(event, make_server())

    assert "&lt;b&gt;95%&lt;/b&gt;" in text


def test_format_alert_escapes_server_name():
    event = AlertEvent("web1", "cpu", "enter", "CPU 95%")
    text = format_alert(event, make_unsafe_server())

    assert "A&lt;B&gt;&amp;C" in text


def test_confirm_prompt_escapes_name_and_command():
    text = confirm_prompt("Выполнить на {name}:", make_unsafe_server(), "echo <hi>")

    assert "A&lt;B&gt;&amp;C" in text
    assert "&lt;hi&gt;" in text
    assert "<hi>" not in text


def test_probe_error_text_distinguishes_parse_and_unavailable():
    from bot.collectors.system import CollectorError
    from bot.ssh.pool import ServerUnavailable

    assert probe_error_text(ServerUnavailable("boom")) == "недоступен"
    assert probe_error_text(CollectorError("bad")) == "ошибка данных"
