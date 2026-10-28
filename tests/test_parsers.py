"""Parsing of the GitHub page, the LeetCode payload, /proc and the cache."""

from __future__ import annotations

import datetime as dt
import json

import pytest

from desk_widgets.data import cache, github, leetcode, system

GH_HTML = """
<table class="ContributionCalendar-grid">
<td tabindex="0" data-ix="0" data-date="2026-10-26" id="cell-0" data-level="1"
    role="gridcell" class="ContributionCalendar-day"></td>
<td data-level="4" data-date="2026-10-27" id="cell-1" class="ContributionCalendar-day"></td>
<td data-date="2026-10-28" id="cell-2" data-level="0"></td>
<td class="ContributionCalendar-day"></td>
</table>
<tool-tip for="cell-0" class="sr-only">10 contributions on October 26th.</tool-tip>
<tool-tip for="cell-1" class="sr-only">31 contributions on October 27th.</tool-tip>
<tool-tip for="cell-2" class="sr-only">No contributions on October 28th.</tool-tip>
"""


def test_github_parses_dates_levels_and_counts():
    days = github.parse_contributions(GH_HTML)
    assert [(d.date.isoformat(), d.count, d.level) for d in days] == [
        ("2026-10-26", 10, 1),
        ("2026-10-27", 31, 4),
        ("2026-10-28", 0, 0),
    ]


def test_github_ignores_cells_without_a_date():
    assert len(github.parse_contributions(GH_HTML)) == 3


def test_github_falls_back_to_the_level_when_no_tooltip_matches():
    html = '<td data-date="2026-10-27" data-level="3" id="x"></td>'
    (day,) = github.parse_contributions(html)
    assert day.count == 3 and day.level == 3


def test_github_returns_nothing_for_an_unrelated_page():
    assert github.parse_contributions("<html><body>404</body></html>") == []


def leetcode_payload(calendar: dict[str, int]) -> str:
    return json.dumps(
        {"data": {"matchedUser": {"userCalendar": {"submissionCalendar": json.dumps(calendar)}}}}
    )


def test_leetcode_parses_the_nested_calendar():
    # 1767398400 is 2026-01-03T00:00:00Z.
    days = leetcode.parse_calendar(leetcode_payload({"1767398400": 3, "1767484800": 12}))
    assert [(d.date.isoformat(), d.count, d.level) for d in days] == [
        ("2026-01-03", 3, 2),
        ("2026-01-04", 12, 4),
    ]


def test_leetcode_honours_custom_thresholds():
    (day,) = leetcode.parse_calendar(leetcode_payload({"1767398400": 3}), [5, 10])
    assert day.level == 1


def test_leetcode_empty_calendar_is_not_an_error():
    assert leetcode.parse_calendar(leetcode_payload({})) == []


def test_leetcode_raises_on_graphql_errors():
    payload = json.dumps({"errors": [{"message": "no permission"}], "data": {"matchedUser": None}})
    with pytest.raises(ValueError, match="no permission"):
        leetcode.parse_calendar(payload)


def test_leetcode_raises_for_an_unknown_user():
    with pytest.raises(ValueError, match="unknown"):
        leetcode.parse_calendar(json.dumps({"data": {"matchedUser": None}}))


PROC_STAT = "cpu  100 0 100 700 100 0 0 0 0 0\ncpu0 1 2 3 4 5 6 7 8 9 10\n"


def test_cpu_times_sum_idle_and_iowait():
    assert system.parse_cpu_times(PROC_STAT) == (800, 1000)


def test_cpu_times_needs_an_aggregate_line():
    with pytest.raises(ValueError, match="/proc/stat"):
        system.parse_cpu_times("cpu0 1 2 3 4 5 6 7 8\n")


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        ((800, 1000), (900, 1200), 0.5),
        ((800, 1000), (800, 1000), 0.0),  # no time passed
        ((800, 1000), (800, 1200), 1.0),  # all busy
    ],
)
def test_cpu_fraction(previous, current, expected):
    assert system.cpu_fraction(previous, current) == pytest.approx(expected)


def test_meminfo_prefers_available_over_free():
    text = "MemTotal:       16000 kB\nMemFree:  1000 kB\nMemAvailable:    4000 kB\nSwap: 1 kB\n"
    assert system.parse_meminfo(text) == (12000, 16000)


def test_meminfo_falls_back_to_free():
    assert system.parse_meminfo("MemTotal: 16000 kB\nMemFree: 4000 kB\n") == (12000, 16000)


def test_cache_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache.save("github-octocat", [["2026-10-01", 1, 1]])
    data, age = cache.load("github-octocat")
    assert data == [["2026-10-01", 1, 1]]
    assert 0 <= age < 5


def test_cache_miss_is_quiet(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert cache.load("nothing-here") == (None, 0.0)


def test_cache_survives_a_corrupt_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    path = tmp_path / "desk-widgets" / "broken.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json")
    assert cache.load("broken") == (None, 0.0)


def test_days_sort_by_date():
    days = github.parse_contributions(GH_HTML)
    assert days == sorted(days)
    assert days[-1].date == dt.date(2026, 10, 28)
