"""Clock widget: large time, date below, in a plain, boxed or split style."""

from __future__ import annotations

import time
from typing import Any

import cairo

from .. import shapes, theme
from .base import BaseWidget


class ClockWidget(BaseWidget):
    """Shows the local time and date."""

    widget_name = "clock"
    title_text = "Clock"

    @property
    def tick_seconds(self) -> float:
        """Tick every second only when seconds are shown."""
        return 1.0 if self.cfg["show"]["seconds"] else 2.0

    def _strings(self) -> tuple[str, str]:
        """Current time and date text, per the configured formats."""
        c = self.cfg["clock"]
        fmt = c["seconds_format"] if self.cfg["show"]["seconds"] else c["time_format"]
        now = time.localtime()
        return time.strftime(fmt, now), time.strftime(c["date_format"], now)

    def accessible_text(self) -> str:
        """Read the time and date out as one line."""
        clock, date = self._strings()
        return f"{clock}, {date}" if self.cfg["show"]["date"] else clock

    def _layout(self, cr: cairo.Context, text: str, role: str) -> Any:
        """Lay out text in one of the configured font roles."""
        return shapes.text_layout(
            cr, text, self.cfg["font"][role], self.cfg["font"]["family"], self.font_scale
        )

    def draw(self, cr: cairo.Context, x: float, y: float, w: float, h: float) -> None:
        """Stack the configured elements, in the configured order, centred."""
        c = self.cfg
        gap = c["layout"]["spacing"] * self.scale
        pad = c["layout"]["padding"] * self.scale / 2
        clock_text, date_text = self._strings()
        style = c["clock"]["style"]
        boxed = style in ("boxed", "split")

        rows: list[tuple[str, Any, str, str, float]] = []  # name, layout, colour, align, extra
        for element in theme.ordered(c, {"title", "value", "date"}):
            if not c["show"][element]:
                continue
            if element == "title":
                if not c["clock"]["title"]:
                    continue
                rows.append(("title", self._layout(cr, c["clock"]["title"], "title"),
                             theme.color(c, "title"), theme.align(c, "title"), 0.0))
            elif element == "value":
                rows.append(("value", self._layout(cr, clock_text, "value"),
                             theme.color(c, "value"), theme.align(c, "value"),
                             2 * pad if boxed else 0.0))
            else:
                rows.append(("date", self._layout(cr, date_text, "date"),
                             theme.color(c, "date"), theme.align(c), 0.0))
        if not rows:
            return

        heights = [lay.get_pixel_size()[1] + extra for _, lay, _, _, extra in rows]
        cursor = y + max((h - sum(heights) - gap * (len(rows) - 1)), 0.0) / 2

        for (name, lay, color, align, _), height in zip(rows, heights, strict=True):
            if name == "value" and style == "split":
                self._draw_split(cr, clock_text, x, cursor, w, height, pad, align)
            elif name == "value" and style == "boxed":
                self._draw_boxed(cr, lay, x, cursor, w, height, pad, align, color)
            else:
                shapes.draw_text(cr, lay, x, cursor, color, align, w)
            cursor += height + gap

    def _box(self, cr: cairo.Context, x: float, y: float, w: float, h: float) -> None:
        """Fill one rounded holder box behind the digits."""
        c = self.cfg
        shapes.fill_box(
            cr, lambda: shapes.shape_path(cr, c["shape"]["cell"], x, y, w, h,
                                          c["shape"]["cell_radius"] * self.scale * 2),
            c["colors"]["track"], 1.0, c["bar_gradient"], (x, y, w, h),
        )

    def _draw_boxed(self, cr: cairo.Context, lay: Any, x: float, y: float, w: float,
                    h: float, pad: float, align: str, color: str) -> None:
        tw = lay.get_pixel_size()[0]
        bx = x
        if align == "center":
            bx = x + (w - tw - 2 * pad) / 2
        elif align == "end":
            bx = x + w - tw - 2 * pad
        self._box(cr, bx, y, tw + 2 * pad, h)
        shapes.draw_text(cr, lay, bx + pad, y + pad, color, "start", tw)

    def _draw_split(self, cr: cairo.Context, text: str, x: float, y: float, w: float,
                    h: float, pad: float, align: str) -> None:
        """Draw each colon-separated group of digits in its own box."""
        parts = text.split(":")
        layouts = [self._layout(cr, part, "value") for part in parts]
        widths = [lay.get_pixel_size()[0] + 2 * pad for lay in layouts]
        gap = self.cfg["layout"]["spacing"] * self.scale
        total = sum(widths) + gap * (len(parts) - 1)
        cursor = x
        if align == "center":
            cursor = x + (w - total) / 2
        elif align == "end":
            cursor = x + w - total
        for lay, width in zip(layouts, widths, strict=True):
            self._box(cr, cursor, y, width, h)
            shapes.draw_text(cr, lay, cursor + pad, y + pad, theme.color(self.cfg, "value"),
                             "start")
            cursor += width + gap
