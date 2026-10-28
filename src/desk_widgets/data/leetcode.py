"""LeetCode submission calendar, from the public GraphQL endpoint."""

from __future__ import annotations

import datetime as dt
import json
import urllib.request

from .grid import Day, level_for

URL = "https://leetcode.com/graphql"
USER_AGENT = "gnome-desk-widgets (+https://github.com/himayurjogade/gnome-desk-widgets)"
QUERY = (
    "query userCalendar($username: String!, $year: Int) {"
    " matchedUser(username: $username) {"
    " userCalendar(year: $year) { submissionCalendar } } }"
)
#: Submissions per day needed for levels 1-4.
LEVELS = [1, 3, 6, 10]


def parse_calendar(payload: str | dict, thresholds: list[int] | None = None) -> list[Day]:
    """Parse a GraphQL response into days. The calendar is JSON inside JSON."""
    blob = json.loads(payload) if isinstance(payload, str) else payload
    if blob.get("errors"):
        raise ValueError(blob["errors"][0].get("message", "GraphQL error"))
    user = (blob.get("data") or {}).get("matchedUser")
    if not user:
        raise ValueError("unknown LeetCode user")
    calendar = json.loads((user.get("userCalendar") or {}).get("submissionCalendar") or "{}")
    levels = thresholds or LEVELS
    days = []
    for timestamp, count in calendar.items():
        date = dt.datetime.fromtimestamp(int(timestamp), dt.UTC).date()
        days.append(Day(date, int(count), level_for(int(count), levels)))
    return sorted(days)


def _query(username: str, year: int, timeout: float,
           thresholds: list[int] | None = None) -> list[Day]:
    body = json.dumps(
        {"query": QUERY, "variables": {"username": username, "year": year}}
    ).encode()
    request = urllib.request.Request(
        URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "Referer": "https://leetcode.com",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return parse_calendar(response.read().decode(), thresholds)


def fetch(username: str, weeks: int = 26, timeout: float = 8.0,
          thresholds: list[int] | None = None) -> list[Day]:
    """Fetch the calendar, adding last year when the grid reaches back into it."""
    today = dt.date.today()
    years = {today.year, (today - dt.timedelta(weeks=weeks)).year}
    days: list[Day] = []
    for year in sorted(years):
        days.extend(_query(username, year, timeout, thresholds))
    return sorted(days)
