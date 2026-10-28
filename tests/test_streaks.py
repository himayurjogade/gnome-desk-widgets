"""Current and longest streak counting."""

from __future__ import annotations

import datetime as dt

import pytest

from desk_widgets.data.grid import Day, current_streak, level_for, longest_streak

TODAY = dt.date(2026, 10, 28)


def days(*specs: tuple[str, int]) -> list[Day]:
    """Build days from ``("2026-10-28", count)`` pairs."""
    return [Day(dt.date.fromisoformat(d), c, 1 if c else 0) for d, c in specs]


def run(start: str, length: int, count: int = 1) -> list[Day]:
    """A run of ``length`` consecutive days starting at ``start``."""
    first = dt.date.fromisoformat(start)
    return [Day(first + dt.timedelta(days=i), count, 1) for i in range(length)]


def test_no_data_is_no_streak():
    assert current_streak([], TODAY) == 0
    assert longest_streak([]) == 0


def test_streak_counts_back_from_today():
    assert current_streak(run("2026-10-24", 5), TODAY) == 5


def test_today_not_done_yet_does_not_break_the_streak():
    # Nothing today, but yesterday and before are active: the day is not over.
    assert current_streak(run("2026-10-24", 4), TODAY) == 4


def test_blank_today_and_yesterday_ends_the_streak():
    assert current_streak(run("2026-10-20", 5), TODAY) == 0


def test_zero_count_today_is_the_same_as_missing():
    data = run("2026-10-24", 4) + days(("2026-10-28", 0))
    assert current_streak(data, TODAY) == 4


def test_gaps_break_the_streak():
    data = run("2026-10-20", 3) + run("2026-10-26", 3)
    assert current_streak(data, TODAY) == 3
    assert longest_streak(data) == 3


def test_longest_streak_finds_the_best_run():
    data = run("2026-01-01", 9) + run("2026-03-01", 4) + run("2026-10-27", 2)
    assert longest_streak(data) == 9


def test_longest_streak_ignores_duplicate_dates():
    data = run("2026-05-01", 3) + run("2026-05-01", 3)
    assert longest_streak(data) == 3


def test_level_counted_as_activity_when_counts_are_missing():
    data = [Day(TODAY, 0, 2), Day(TODAY - dt.timedelta(days=1), 0, 1)]
    assert current_streak(data, TODAY) == 2


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, 0), (1, 1), (2, 1), (3, 2), (5, 2), (6, 3), (9, 3), (10, 4), (99, 4)],
)
def test_level_for_thresholds(count, expected):
    assert level_for(count, [1, 3, 6, 10]) == expected


def test_level_for_never_reports_zero_for_activity():
    assert level_for(1, [5, 10]) == 1
