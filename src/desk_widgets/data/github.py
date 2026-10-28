"""GitHub contribution data, scraped from the public contributions fragment."""

from __future__ import annotations

import datetime as dt
import re
import urllib.parse
import urllib.request

from .grid import Day

URL = "https://github.com/users/{username}/contributions"
USER_AGENT = "gnome-desk-widgets (+https://github.com/himayurjogade/gnome-desk-widgets)"

_CELL = re.compile(r"<td\b[^>]*\bdata-date=[^>]*>", re.I)
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')
_TOOLTIP = re.compile(r'<tool-tip\b[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', re.I)
_COUNT = re.compile(r"^\s*(\d+)")


def parse_contributions(html: str) -> list[Day]:
    """Pull ``data-date``/``data-level`` cells, and counts from their tooltips."""
    counts = {
        cell_id: int(m.group(1)) if (m := _COUNT.match(text)) else 0
        for cell_id, text in _TOOLTIP.findall(html)
    }
    days = []
    for tag in _CELL.findall(html):
        attrs = dict(_ATTR.findall(tag))
        try:
            date = dt.date.fromisoformat(attrs["data-date"])
            level = int(attrs.get("data-level", 0))
        except (KeyError, ValueError):
            continue
        count = counts.get(attrs.get("id", ""), 0)
        days.append(Day(date, count or level, level))
    return sorted(days)


def fetch(username: str, weeks: int = 53, timeout: float = 8.0) -> list[Day]:
    """Download and parse one user's contribution calendar (last year)."""
    request = urllib.request.Request(
        URL.format(username=urllib.parse.quote(username)),
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        html = response.read().decode("utf-8", "replace")
    days = parse_contributions(html)
    if not days:
        raise ValueError(f"no contribution cells for {username!r}")
    return days
