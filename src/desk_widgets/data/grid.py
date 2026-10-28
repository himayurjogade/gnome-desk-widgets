"""Streak maths and contribution-grid layout. Pure functions, no GTK."""

from __future__ import annotations

import datetime as dt
from typing import Any, NamedTuple


class Day(NamedTuple):
    """One day of activity."""

    date: dt.date
    count: int
    level: int


#: Column index within a week, by the configured first day of the week.
def row_of(date: dt.date, week_start: str = "sunday") -> int:
    """Row 0-6 for ``date``, counting from the configured first weekday."""
    return date.weekday() if week_start == "monday" else (date.weekday() + 1) % 7


def level_for(count: int, thresholds: list[int]) -> int:
    """Map a count onto an activity level, 0 for none."""
    if count <= 0:
        return 0
    return sum(1 for t in thresholds if count >= t) or 1


def current_streak(days: list[Day], today: dt.date | None = None) -> int:
    """Consecutive active days ending today.

    A blank *today* does not break the streak - the day is not over yet - so
    counting then starts at yesterday.
    """
    today = today or dt.date.today()
    active = {d.date for d in days if d.count > 0 or d.level > 0}
    if not active:
        return 0
    cursor = today if today in active else today - dt.timedelta(days=1)
    streak = 0
    while cursor in active:
        streak += 1
        cursor -= dt.timedelta(days=1)
    return streak


def longest_streak(days: list[Day]) -> int:
    """Longest run of consecutive active days in the data."""
    active = sorted({d.date for d in days if d.count > 0 or d.level > 0})
    best = run = 0
    previous: dt.date | None = None
    for date in active:
        run = run + 1 if previous and date - previous == dt.timedelta(days=1) else 1
        best = max(best, run)
        previous = date
    return best


def build_grid(days: list[Day], weeks: int, week_start: str = "sunday",
               today: dt.date | None = None) -> list[list[Day | None]]:
    """Lay days out as ``weeks`` columns of 7 rows, newest column last.

    Missing days become zero-count days; days after *today* are ``None`` so the
    last column can be partly empty, like GitHub's own grid.
    """
    today = today or dt.date.today()
    known = {d.date: d for d in days}
    last_start = today - dt.timedelta(days=row_of(today, week_start))
    grid: list[list[Day | None]] = []
    for column in range(weeks):
        start = last_start - dt.timedelta(weeks=weeks - 1 - column)
        cells: list[Day | None] = []
        for row in range(7):
            date = start + dt.timedelta(days=row)
            cells.append(None if date > today else known.get(date, Day(date, 0, 0)))
        grid.append(cells)
    return grid


def dump(days: list[Day]) -> list[list[Any]]:
    """Days as JSON-safe rows, for the cache."""
    return [[d.date.isoformat(), d.count, d.level] for d in days]


def restore(rows: Any) -> list[Day]:
    """Rebuild days from :func:`dump` output, dropping anything malformed."""
    days = []
    for row in rows or []:
        try:
            days.append(Day(dt.date.fromisoformat(row[0]), int(row[1]), int(row[2])))
        except (TypeError, ValueError, IndexError):
            continue
    return days
