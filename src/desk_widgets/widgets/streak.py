"""Shared base for the contribution-grid widgets (GitHub, LeetCode)."""

from __future__ import annotations

import datetime as dt
import logging
import threading
from collections.abc import Callable
from functools import partial
from typing import Any

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from .. import shapes, theme
from ..data import cache
from ..data.grid import Day, build_grid, current_streak, dump, longest_streak, restore
from .base import BaseWidget

log = logging.getLogger(__name__)


def human_age(seconds: float) -> str:
    """A short "3m"/"5h"/"2d" string for how old cached data is."""
    for limit, unit, step in ((3600, "m", 60), (86400, "h", 3600), (None, "d", 86400)):
        if limit is None or seconds < limit:
            return f"{int(seconds // step)}{unit}"
    return "?"


class StreakWidget(BaseWidget):
    """Draws a contribution grid plus current and longest streak.

    Subclasses supply :attr:`fetcher`; it runs on a background thread, its
    result is cached on disk and the last good data is shown when offline.
    """

    fetcher: Callable[..., list[Day]]
    unit = "contributions"
    _hover: dt.date | None = None

    def __init__(self, app: Gtk.Application, cfg: dict[str, Any]) -> None:
        super().__init__(app, cfg)
        self.section = cfg[self.widget_name]
        self.username = str(self.section["username"])
        self.palette = cfg["palettes"].get(self.section["palette"],
                                           cfg["palettes"]["github"])
        self._cells: list[tuple[float, float, float, Day]] = []
        self.error: str | None = None

        cached, age = cache.load(f"{self.widget_name}-{self.username}")
        self.days = restore(cached)
        self.stale = bool(self.days)
        self.age = age

        self.area.set_has_tooltip(True)
        self.area.connect("query-tooltip", self._on_tooltip)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", lambda *_: self._set_hover(None))
        self.area.add_controller(motion)
        self._start_fetch()
        self._timers.append(
            GLib.timeout_add_seconds(
                max(int(cfg["behavior"]["remote_interval"]), 30),
                lambda: self._start_fetch() or GLib.SOURCE_CONTINUE,
            )
        )

    # --- data -------------------------------------------------------------
    @property
    def tick_seconds(self) -> float:
        """Only used to keep the "stale" age label current."""
        return 60.0

    def _start_fetch(self) -> None:
        """Fetch in the background; the UI thread is never blocked."""
        threading.Thread(target=self._worker, daemon=True).start()

    def fetch_days(self, weeks: int, timeout: float) -> list[Day]:
        """Call the subclass fetcher. Runs off the UI thread."""
        return type(self).fetcher(self.username, weeks, timeout)

    def _worker(self) -> None:
        try:
            days = self.fetch_days(
                int(self.cfg["behavior"]["grid_weeks"]), float(self.section["timeout"])
            )
        except (OSError, ValueError) as exc:  # URLError and HTTPError are OSErrors
            GLib.idle_add(self._failed, str(exc))
            return
        GLib.idle_add(self._loaded, days)

    def _loaded(self, days: list[Day]) -> bool:
        if not self._timers:  # the window was closed while we were fetching
            return GLib.SOURCE_REMOVE
        self.days, self.stale, self.error, self.age = days, False, None, 0.0
        cache.save(f"{self.widget_name}-{self.username}", dump(days))
        self.update_now()
        self.area.queue_draw()
        return GLib.SOURCE_REMOVE

    def _failed(self, message: str) -> bool:
        if not self._timers:
            return GLib.SOURCE_REMOVE
        log.warning("%s: fetch failed (%s)", self.widget_name, message)
        self.error, self.stale = message, True
        self.update_now()
        self.area.queue_draw()
        return GLib.SOURCE_REMOVE

    def accessible_text(self) -> str:
        """Summarise the streaks for a screen reader."""
        if not self.days:
            return f"{self.section['title']} {self.username}: no data yet"
        total = sum(d.count for d in self.days)
        state = f", data is {human_age(self.age)} old" if self.stale else ""
        return (
            f"{self.section['title']} {self.username}: "
            f"current streak {current_streak(self.days)} days, "
            f"longest streak {longest_streak(self.days)} days, "
            f"{total} {self.unit} on record{state}"
        )

    # --- drawing ----------------------------------------------------------
    def _text(self, cr: cairo.Context, text: str, role: str, scale: float = 1.0) -> Any:
        return shapes.text_layout(cr, text, self.cfg["font"][role],
                                  self.cfg["font"]["family"], self.font_scale * scale)

    def _set_hover(self, date: dt.date | None) -> None:
        """Highlight one grid cell under the pointer, or none.

        Skipped under ``behavior.reduced_motion``: nothing changes as the
        pointer moves, and the tooltip still names the day.
        """
        if self.cfg["behavior"]["reduced_motion"]:
            return
        if date != self._hover:
            self._hover = date
            self.area.queue_draw()

    def _on_motion(self, _controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        self._set_hover(next((d.date for cx, cy, size, d in self._cells
                              if cx <= x <= cx + size and cy <= y <= cy + size), None))

    def _on_tooltip(self, _area: Gtk.Widget, x: int, y: int, _kb: bool,
                    tooltip: Gtk.Tooltip) -> bool:
        """Name the day under the pointer, so colour is never the only signal."""
        for cx, cy, size, day in self._cells:
            if cx <= x <= cx + size and cy <= y <= cy + size:
                tooltip.set_text(f"{day.count} {self.unit} on {day.date:%d %b %Y}")
                return True
        return False

    def _element_height(self, cr: cairo.Context, element: str) -> float:
        """Height one stacked element needs; the grid takes whatever is left."""
        c = self.cfg
        if element == "title":
            return self._text(cr, "X", "title").get_pixel_size()[1]
        if element == "value":
            return self._text(cr, "0", "value").get_pixel_size()[1]
        if element == "legend":
            return max(self._text(cr, "X", "legend").get_pixel_size()[1],
                       c["shape"]["cell_size"] * self.scale * 0.8)
        return 0.0

    def _visible(self, element: str) -> bool:
        show = self.cfg["show"]
        if element == "legend":
            return show["legend"] or self.stale
        return bool(show[element])

    def draw(self, cr: cairo.Context, x: float, y: float, w: float, h: float) -> None:
        """Lay the configured elements out top to bottom; the grid fills the rest."""
        c = self.cfg
        gap = c["layout"]["spacing"] * self.scale
        items = [e for e in theme.ordered(c, {"title", "value", "grid", "legend"})
                 if self._visible(e)]
        if not items:
            return
        heights = {e: self._element_height(cr, e) for e in items}
        spare = h - sum(heights.values()) - gap * (len(items) - 1)

        cursor = y
        for element in items:
            height = max(spare, 0.0) if element == "grid" else heights[element]
            if element == "title":
                title = self._text(cr, f"{self.section['title']} · {self.username}".upper(),
                                   "title")
                shapes.draw_text(cr, title, x, cursor, theme.color(c, "title"),
                                 theme.align(c, "title"), w)
            elif element == "value":
                self._draw_streaks(cr, x, cursor, w, height)
            elif element == "legend":
                self._draw_legend(cr, x, cursor, w, height)
            else:
                self._draw_grid(cr, x, cursor, w, height)
            cursor += height + gap

    def _draw_streaks(self, cr: cairo.Context, x: float, y: float, w: float,
                      height: float) -> float:
        """Current streak in the value font, longest beside it."""
        c = self.cfg
        current = current_streak(self.days) if self.days else 0
        value = self._text(cr, f"{current}", "value")
        unit = self._text(cr, " day streak", "small")
        vw = value.get_pixel_size()[0]
        align = theme.align(c, "value")
        offset = 0.0
        if align == "end":
            offset = w - vw - unit.get_pixel_size()[0]
        elif align == "center":
            offset = (w - vw - unit.get_pixel_size()[0]) / 2
        baseline = y + height - unit.get_pixel_size()[1] * 1.2
        shapes.draw_text(cr, value, x + offset, y, theme.color(c, "value"), "start")
        shapes.draw_text(cr, unit, x + offset + vw + 4 * self.scale, baseline,
                         theme.color(c, "label"), "start")
        if c["show"]["longest_streak"] and self.days:
            longest = self._text(cr, f"longest {longest_streak(self.days)}", "small")
            shapes.draw_text(cr, longest, x, baseline, theme.color(c, "label"), "end", w)
        return height

    def _draw_legend(self, cr: cairo.Context, x: float, y: float, w: float,
                     height: float) -> None:
        """Legend on the left, an offline or stale marker on the right."""
        c = self.cfg
        cell = c["shape"]["cell_size"] * self.scale * 0.8
        gap = c["shape"]["cell_gap"] * self.scale
        if c["show"]["legend"]:
            less = self._text(cr, "Less", "legend")
            more = self._text(cr, "More", "legend")
            shapes.draw_text(cr, less, x, y, theme.color(c, "legend"), "start")
            cursor = x + less.get_pixel_size()[0] + gap * 2
            for color in self.palette:
                self._cell(cr, cursor, y + (height - cell) / 2, cell, color)
                cursor += cell + gap
            shapes.draw_text(cr, more, cursor + gap, y, theme.color(c, "legend"), "start")
        if self.stale:
            label = "offline" if not self.days else f"stale · {human_age(self.age)}"
            shapes.draw_text(cr, self._text(cr, label, "legend"), x, y,
                             theme.color(c, "legend"), "end", w)

    def _cell(self, cr: cairo.Context, x: float, y: float, size: float, color: str,
              outline: str = "") -> None:
        """One grid or legend cell in the configured cell shape."""
        c = self.cfg
        path = partial(shapes.shape_path, cr, c["shape"]["cell"], x, y, size, size,
                       c["shape"]["cell_radius"] * self.scale)
        path()
        shapes.set_color(cr, color)
        cr.fill()
        border = outline or theme.color(c, "grid_border")
        if border:
            path()
            shapes.set_color(cr, border)
            cr.set_line_width(max(1.0, self.scale))
            cr.stroke()

    def _draw_grid(self, cr: cairo.Context, x: float, y: float, w: float, h: float) -> None:
        """GitHub's 7-row layout, newest week on the right."""
        c = self.cfg
        weeks = int(c["behavior"]["grid_weeks"])
        gap = c["shape"]["cell_gap"] * self.scale
        size = min(c["shape"]["cell_size"] * self.scale,
                   (w - gap * (weeks - 1)) / weeks, (h - gap * 6) / 7)
        if size <= 0:
            return
        grid = build_grid(self.days, weeks, c["behavior"]["week_start"])
        empty = theme.color(c, "grid_empty")
        hover = theme.color(c, "hover")
        self._cells = []
        for column, cells in enumerate(grid):
            cx = x + column * (size + gap)
            for row, day in enumerate(cells):
                if day is None:
                    continue
                cy = y + row * (size + gap)
                level = min(day.level, len(self.palette) - 1)
                outline = hover if self._hover == day.date else ""
                self._cell(cr, cx, cy, size, self.palette[level] if day.count else empty,
                           outline)
                self._cells.append((cx, cy, size, day))
