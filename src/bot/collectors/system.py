from __future__ import annotations

import re
from dataclasses import dataclass

from bot.config import ServerConfig
from bot.ssh.pool import SshPool


class CollectorError(Exception):
    pass


@dataclass
class SystemMetrics:
    hostname: str
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    load1: float
    load5: float
    load15: float
    cpu_count: int
    uptime_seconds: float

    @property
    def load_per_cpu(self) -> float:
        if self.cpu_count <= 0:
            return 0.0
        return self.load1 / self.cpu_count


SYSTEM_COMMAND = (
    "echo '###HOST'; hostname; "
    "echo '###LOAD'; cat /proc/loadavg; "
    "echo '###NPROC'; nproc; "
    "echo '###UPTIME'; cat /proc/uptime; "
    "echo '###MEM'; cat /proc/meminfo; "
    "echo '###DF'; df -P /; "
    "echo '###CPU1'; grep '^cpu ' /proc/stat; "
    "sleep 1; "
    "echo '###CPU2'; grep '^cpu ' /proc/stat"
)

_SECTION_RE = re.compile(r"^###([A-Z0-9]+)$")


def _split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = _SECTION_RE.match(line.strip())
        if match:
            current = match.group(1)
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _require(sections: dict[str, str], name: str) -> str:
    value = sections.get(name)
    if not value:
        raise CollectorError(f"Missing section {name} in system output")
    return value


def _cpu_values(line: str) -> list[int]:
    columns = line.split()
    if not columns or columns[0] != "cpu" or len(columns) < 5:
        raise CollectorError("Cannot parse /proc/stat")
    try:
        return [int(column) for column in columns[1:]]
    except ValueError as exc:
        raise CollectorError("Cannot parse /proc/stat") from exc


def parse_cpu_stat(first: str, second: str) -> float:
    values_first = _cpu_values(first)
    values_second = _cpu_values(second)
    total_delta = sum(values_second) - sum(values_first)
    idle_delta = (values_second[3] + values_second[4]) - (
        values_first[3] + values_first[4]
    )
    if total_delta <= 0:
        raise CollectorError("Cannot compute CPU usage from /proc/stat")
    return round((1.0 - idle_delta / total_delta) * 100.0, 1)


def parse_meminfo(mem_section: str) -> float:
    values: dict[str, float] = {}
    for line in mem_section.splitlines():
        parts = line.split(":")
        if len(parts) != 2:
            continue
        key = parts[0].strip()
        number = parts[1].strip().split()
        if number:
            values[key] = float(number[0])
    if "MemTotal" not in values or "MemAvailable" not in values:
        raise CollectorError("Cannot parse MemTotal/MemAvailable")
    total = values["MemTotal"]
    if total <= 0:
        raise CollectorError("MemTotal is zero")
    return round((total - values["MemAvailable"]) / total * 100.0, 1)


def parse_df(df_section: str) -> float:
    for line in df_section.splitlines()[1:]:
        columns = line.split()
        if len(columns) >= 5 and columns[4].endswith("%"):
            return float(columns[4].rstrip("%"))
    raise CollectorError("Cannot parse df output")


def parse_loadavg(load_section: str) -> tuple[float, float, float]:
    columns = load_section.split()
    if len(columns) < 3:
        raise CollectorError("Cannot parse /proc/loadavg")
    return float(columns[0]), float(columns[1]), float(columns[2])


def parse_uptime(uptime_section: str) -> float:
    columns = uptime_section.split()
    if not columns:
        raise CollectorError("Cannot parse /proc/uptime")
    return float(columns[0])


def parse_system_output(text: str) -> SystemMetrics:
    sections = _split_sections(text)
    load1, load5, load15 = parse_loadavg(_require(sections, "LOAD"))
    cpu_count = int(_require(sections, "NPROC").split()[0])
    return SystemMetrics(
        hostname=_require(sections, "HOST").splitlines()[0].strip(),
        cpu_percent=parse_cpu_stat(
            _require(sections, "CPU1"), _require(sections, "CPU2")
        ),
        ram_percent=parse_meminfo(_require(sections, "MEM")),
        disk_percent=parse_df(_require(sections, "DF")),
        load1=load1,
        load5=load5,
        load15=load15,
        cpu_count=cpu_count,
        uptime_seconds=parse_uptime(_require(sections, "UPTIME")),
    )


async def collect_system(pool: SshPool, server: ServerConfig) -> SystemMetrics:
    result = await pool.run(server, SYSTEM_COMMAND)
    if result.exit_status != 0 and not result.stdout:
        raise CollectorError(result.stderr or "system metrics command failed")
    return parse_system_output(result.stdout)
