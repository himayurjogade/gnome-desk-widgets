"""CPU, memory and disk readings from /proc and statvfs."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import NamedTuple


class Reading(NamedTuple):
    """One gauge: a 0-1 fraction plus the text to print beside it."""

    key: str
    label: str
    fraction: float
    text: str


def parse_cpu_times(text: str) -> tuple[int, int]:
    """Return ``(idle, total)`` jiffies from the aggregate line of /proc/stat."""
    for line in text.splitlines():
        if line.startswith("cpu "):
            values = [int(v) for v in line.split()[1:]]
            idle = sum(values[3:5])  # idle + iowait
            return idle, sum(values)
    raise ValueError("no 'cpu' line in /proc/stat")


def cpu_fraction(previous: tuple[int, int], current: tuple[int, int]) -> float:
    """Busy fraction between two /proc/stat samples."""
    idle = current[0] - previous[0]
    total = current[1] - previous[1]
    if total <= 0:
        return 0.0
    return min(max(1 - idle / total, 0.0), 1.0)


def parse_meminfo(text: str) -> tuple[int, int]:
    """Return ``(used_kb, total_kb)`` from /proc/meminfo."""
    fields = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        if key in ("MemTotal", "MemAvailable", "MemFree"):
            fields[key] = int(rest.split()[0])
    total = fields.get("MemTotal", 0)
    available = fields.get("MemAvailable", fields.get("MemFree", 0))
    return max(total - available, 0), total


def human_gb(kilobytes: float) -> str:
    """Kilobytes as a short gigabyte string."""
    return f"{kilobytes / 1024 / 1024:.1f}G"


class SystemStats:
    """Samples CPU, RAM and disk. CPU needs two samples, so it starts at 0."""

    def __init__(self, disk_path: str = "/") -> None:
        self.disk_path = disk_path
        self._cpu = self._read_cpu()

    def _read_cpu(self) -> tuple[int, int]:
        return parse_cpu_times(Path("/proc/stat").read_text())

    def cpu(self) -> Reading:
        """Busy fraction since the previous call."""
        current = self._read_cpu()
        fraction = cpu_fraction(self._cpu, current)
        self._cpu = current
        return Reading("cpu", "CPU", fraction, f"{fraction * 100:.0f}%")

    def ram(self) -> Reading:
        """Used memory."""
        used, total = parse_meminfo(Path("/proc/meminfo").read_text())
        fraction = used / total if total else 0.0
        return Reading("ram", "RAM", fraction, f"{human_gb(used)}/{human_gb(total)}")

    def disk(self) -> Reading:
        """Used space on the configured mount point."""
        usage = shutil.disk_usage(self.disk_path)
        fraction = usage.used / usage.total if usage.total else 0.0
        used, total = usage.used / 1024, usage.total / 1024
        return Reading("disk", "DISK", fraction, f"{human_gb(used)}/{human_gb(total)}")

    def sample(self, metrics: list[str]) -> list[Reading]:
        """Read the requested metrics, skipping any that fail."""
        readings = []
        for name in metrics:
            reader = getattr(self, name, None)
            if reader is None:
                continue
            try:
                readings.append(reader())
            except (OSError, ValueError):
                readings.append(Reading(name, name.upper(), 0.0, "n/a"))
        return readings
