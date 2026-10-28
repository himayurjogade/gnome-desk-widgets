"""System stats widget: CPU, RAM and disk as bars, rings or plain numbers."""

from __future__ import annotations

import logging
from functools import partial
from typing import Any

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from .. import shapes, theme
from ..data.system import Reading, SystemStats
from .base import BaseWidget

log = logging.getLogger(__name__)

METRICS = ("cpu", "ram", "disk")

Box = tuple[float, float, float, float]


class SystemWidget(BaseWidget):
    """Live CPU, memory and disk usage."""

    widget_name = "system"
    title_text = "System stats"

    def __init__(self, app: Gtk.Application, cfg: dict[str, Any]) -> None:
        super().__init__(app, cfg)
        self.metrics = [m for m in cfg["system"]["metrics"] if m in METRICS]
        for unknown in set(cfg["system"]["metrics"]) - set(METRICS):
            log.warning("config: system.metrics has unknown metric %r, ignored", unknown)
        self.stats = SystemStats(cfg["system"]["disk_path"])
        self.readings: list[Reading] = self.stats.sample(self.metrics)

    def refresh(self) -> None:
        """Re-sample every metric."""
        self.readings = self.stats.sample(self.metrics)

    def label_for(self, reading: Reading) -> str:
        """The configured label for a metric, falling back to its own."""
        return str(self.cfg["system"]["labels"].get(reading.key, reading.label))

    def accessible_text(self) -> str:
        """Read every gauge out as "CPU 12%, RAM 5.6G/14.6G"."""
        return ", ".join(f"{self.label_for(r)} {r.text}" for r in self.readings)

    # --- layout -----------------------------------------------------------
    def draw(self, cr: cairo.Context, x: float, y: float, w: float, h: float) -> None:
        """Draw the title and one gauge per configured metric."""
        c = self.cfg
        gap = c["layout"]["spacing"] * self.scale
        elements = theme.ordered(c, {"title", "value"})
        gauges: Box | None = None

        for element in elements:
            if element == "title" and c["show"]["title"] and c["system"]["title"]:
                lay = shapes.text_layout(cr, c["system"]["title"], c["font"]["title"],
                                         c["font"]["family"], self.font_scale)
                height = lay.get_pixel_size()[1]
                top = y if elements.index(element) == 0 else y + h - height
                shapes.draw_text(cr, lay, x, top, theme.color(c, "title"),
                                 theme.align(c, "title"), w)
                if elements.index(element) == 0:
                    y, h = y + height + gap, h - height - gap
                else:
                    h -= height + gap
            elif element == "value" and c["show"]["value"]:
                gauges = (x, y, w, h)

        if gauges and self.readings:
            self._draw_gauges(cr, *gauges, gap)

    def _boxes(self, x: float, y: float, w: float, h: float, count: int,
               gap: float) -> list[Box]:
        """Split the content area into one box per metric, along layout.direction."""
        if self.cfg["layout"]["direction"] == "horizontal":
            width = (w - gap * (count - 1)) / count
            return [(x + i * (width + gap), y, width, h) for i in range(count)]
        height = (h - gap * (count - 1)) / count
        return [(x, y + i * (height + gap), w, height) for i in range(count)]

    def _draw_gauges(self, cr: cairo.Context, x: float, y: float, w: float, h: float,
                     gap: float) -> None:
        style = self.cfg["system"]["style"]
        boxes = self._boxes(x, y, w, h, len(self.readings), gap)
        for reading, box in zip(self.readings, boxes, strict=True):
            if style == "ring":
                self._draw_ring(cr, reading, box)
            else:
                self._draw_row(cr, reading, box, numbers=style == "number", gap=gap)

    # --- gauges -----------------------------------------------------------
    def _fit(self, cr: cairo.Context, text: str, role: str, max_w: float,
             max_h: float) -> Any:
        """Lay out text, shrinking the font until it fits the given box."""
        layout = shapes.text_layout(cr, text, self.cfg["font"][role],
                                    self.cfg["font"]["family"], self.font_scale)
        tw, th = layout.get_pixel_size()
        fit = min(max_w / tw if tw else 1.0, max_h / th if th else 1.0, 1.0)
        if fit >= 0.999:
            return layout
        return shapes.text_layout(cr, text, self.cfg["font"][role],
                                  self.cfg["font"]["family"], self.font_scale * fit)

    def _draw_row(self, cr: cairo.Context, reading: Reading, box: Box, numbers: bool,
                  gap: float) -> None:
        """A labelled bar, or just the number when style = number."""
        c = self.cfg
        x, y, w, h = box
        side_by_side = c["layout"]["direction"] == "vertical"
        bar_h = 0.0 if numbers else c["system"]["bar_height"] * self.scale
        label = shapes.text_layout(cr, self.label_for(reading), c["font"]["small"],
                                   c["font"]["family"], self.font_scale)
        lw, label_h = label.get_pixel_size()
        room_w = w - (lw + gap if side_by_side else 0)
        value = self._fit(cr, reading.text, "value" if numbers else "small",
                          max(room_w, 1.0), max(h - bar_h - gap / 2, 1.0))
        value_h = value.get_pixel_size()[1]

        text_h = max(label_h, value_h) if side_by_side else label_h + value_h
        top = y + max(h - (text_h + (0.0 if numbers else gap / 2 + bar_h)), 0.0) / 2
        if side_by_side:
            shapes.draw_text(cr, label, x, top + (text_h - label_h) / 2,
                             theme.color(c, "label"), "start")
            shapes.draw_text(cr, value, x, top + (text_h - value_h) / 2,
                             theme.color(c, "value"), "end", w)
        else:
            shapes.draw_text(cr, label, x, top, theme.color(c, "label"), "center", w)
            shapes.draw_text(cr, value, x, top + label_h, theme.color(c, "value"),
                             "center", w)
        if numbers:
            return

        bar_y = top + text_h + gap / 2
        shapes.fill_box(cr, partial(shapes.pill, cr, x, bar_y, w, bar_h), c["colors"]["track"])
        filled = max(w * reading.fraction, bar_h) if reading.fraction > 0 else 0.0
        if filled:
            shapes.fill_box(cr, partial(shapes.pill, cr, x, bar_y, filled, bar_h),
                            c["colors"]["accent"], 1.0, c["bar_gradient"],
                            (x, bar_y, w, bar_h))

    def _draw_ring(self, cr: cairo.Context, reading: Reading, box: Box) -> None:
        """A ring gauge with the percentage inside and the label below."""
        c = self.cfg
        x, y, w, h = box
        width = c["shape"]["ring_width"] * self.scale
        label = shapes.text_layout(cr, self.label_for(reading), c["font"]["small"],
                                   c["font"]["family"], self.font_scale * 0.85)
        label_h = label.get_pixel_size()[1]
        size = min(c["system"]["ring_size"] * self.scale, w * 0.9, h - label_h)
        radius = max((size - width) / 2, width)
        cx, cy = x + w / 2, y + (h - label_h) / 2

        shapes.set_color(cr, c["colors"]["track"])
        shapes.ring(cr, cx, cy, radius, width)
        shapes.set_color(cr, c["colors"]["accent"])
        shapes.ring(cr, cx, cy, radius, width, reading.fraction)

        percent = self._fit(cr, f"{reading.fraction * 100:.0f}%", "small",
                            radius * 1.4, radius)
        pw, ph = percent.get_pixel_size()
        shapes.draw_text(cr, percent, cx - pw / 2, cy - ph / 2, theme.color(c, "value"),
                         "start")
        shapes.draw_text(cr, label, x, y + h - label_h, theme.color(c, "label"), "center", w)
