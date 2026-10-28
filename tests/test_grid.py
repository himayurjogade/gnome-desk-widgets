"""Grid layout: 7 rows, week start, and where today lands."""

from __future__ import annotations

import datetime as dt

import pytest

from desk_widgets.data.grid import Day, build_grid, dump, restore, row_of

# A Wednesday.
TODAY = dt.date(2026, 10, 28)


@pytest.mark.parametrize(
    ("date", "sunday_row", "monday_row"),
    [
        ("2026-10-25", 0, 6),  # Sunday
        ("2026-10-26", 1, 0),  # Monday
        ("2026-10-28", 3, 2),  # Wednesday
        ("2026-10-31", 6, 5),  # Saturday
    ],
)
def test_row_of_respects_the_week_start(date, sunday_row, monday_row):
    day = dt.date.fromisoformat(date)
    assert row_of(day, "sunday") == sunday_row
    assert row_of(day, "monday") == monday_row


def test_grid_is_weeks_columns_of_seven():
    grid = build_grid([], 26, "sunday", TODAY)
    assert len(grid) == 26
    assert {len(column) for column in grid} == {7}


def test_today_is_in_the_last_column_and_the_future_is_empty():
    grid = build_grid([], 4, "sunday", TODAY)
    last = grid[-1]
    assert [cell.date for cell in last[:4]] == [
        dt.date(2026, 10, 25), dt.date(2026, 10, 26),
        dt.date(2026, 10, 27), dt.date(2026, 10, 28),
    ]
    assert last[4:] == [None, None, None]


def test_monday_start_shifts_the_whole_grid():
    grid = build_grid([], 4, "monday", TODAY)
    assert grid[-1][0].date == dt.date(2026, 10, 26)  # Monday
    assert grid[-1][2].date == TODAY
    assert grid[-1][3:] == [None, None, None, None]


def test_counts_land_in_the_right_cell():
    day = Day(dt.date(2026, 10, 20), 7, 3)
    grid = build_grid([day], 3, "sunday", TODAY)
    found = [cell for column in grid for cell in column if cell and cell.count]
    assert found == [day]


def test_missing_days_become_empty_days_not_holes():
    grid = build_grid([], 2, "sunday", TODAY)
    past = [cell for column in grid for cell in column if cell]
    assert all(cell.count == 0 and cell.level == 0 for cell in past)
    assert len(past) == 11  # 7 + 4 days of the current week


def test_grid_starts_at_the_first_weekday_of_the_oldest_week():
    grid = build_grid([], 3, "sunday", TODAY)
    assert grid[0][0].date == dt.date(2026, 10, 11)
    assert row_of(grid[0][0].date, "sunday") == 0


def test_dump_and_restore_round_trip():
    data = [Day(dt.date(2026, 10, 1), 3, 2), Day(dt.date(2026, 10, 2), 0, 0)]
    assert restore(dump(data)) == data


def test_restore_skips_malformed_rows():
    assert restore([["2026-10-01", 1, 1], ["nope", 1, 1], [], None]) == [
        Day(dt.date(2026, 10, 1), 1, 1)
    ]
