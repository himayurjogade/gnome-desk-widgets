"""Shared widget window: transparent shaped surface, drag to move, redraw timer."""

from __future__ import annotations

import logging
import math
import os
from typing import Any

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from .. import shapes, theme

log = logging.getLogger(__name__)

_CSS = b"window.desk-widget { background: transparent; box-shadow: none; }"
_css_loaded = False
_warned_position = False


def _load_css() -> None:
    """Install the transparent-window stylesheet once per process."""
    global _css_loaded
    if _css_loaded:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(_CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _css_loaded = True


def text_scale(cfg: dict[str, Any]) -> float:
    """System font scaling factor, or 1.0 when text_scaling is off."""
    if not cfg["behavior"]["text_scaling"]:
        return 1.0
    settings = Gtk.Settings.get_default()
    dpi = settings.get_property("gtk-xft-dpi") if settings else 0
    return (dpi / 1024 / 96) if dpi and dpi > 0 else 1.0


class BaseWidget(Gtk.ApplicationWindow):
    """A standalone, undecorated widget window that draws itself with cairo."""

    widget_name = "base"
    title_text = "Widget"

    def __init__(self, app: Gtk.Application, cfg: dict[str, Any]) -> None:
        super().__init__(application=app)
        self.cfg = cfg
        self.scale = cfg["size"]["scale"]
        self.font_scale = self.scale * text_scale(cfg)
        self._last_text = ""

        _load_css()
        self.add_css_class("desk-widget")
        self.set_title(self.title_text)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(
            int(cfg["size"]["width"] * self.scale), int(cfg["size"]["height"] * self.scale)
        )
        self.update_property([Gtk.AccessibleProperty.LABEL], [self.title_text])

        self.area = Gtk.DrawingArea()
        self.area.set_draw_func(self._on_draw)
        self.area.update_property([Gtk.AccessibleProperty.LABEL], [self.title_text])
        # Gtk.WindowHandle gives compositor-native drag-to-move on Wayland.
        handle = Gtk.WindowHandle()
        handle.set_child(self.area)
        self.set_child(handle)

        esc = Gtk.ShortcutController()
        esc.add_shortcut(
            Gtk.Shortcut(
                trigger=Gtk.ShortcutTrigger.parse_string("Escape"),
                action=Gtk.CallbackAction.new(lambda *_: self.close() or True),
            )
        )
        self.add_controller(esc)

        self._warn_positioning()
        interval = max(int(self.tick_seconds * 1000), 100)
        self._timers = [GLib.timeout_add(interval, self._tick)]
        self.connect("close-request", self._on_close)

    # --- subclass API -----------------------------------------------------
    @property
    def tick_seconds(self) -> float:
        """How often to re-check the data behind the widget."""
        return self.cfg["behavior"]["stats_interval"]

    def refresh(self) -> None:
        """Re-read data. Called on every tick before the redraw check."""

    def accessible_text(self) -> str:
        """The widget's current content as a single string, for screen readers."""
        return self.title_text

    def draw(self, cr: cairo.Context, x: float, y: float, w: float, h: float) -> None:
        """Draw the widget content inside the padded content box."""
        raise NotImplementedError

    # --- internals --------------------------------------------------------
    def _warn_positioning(self) -> None:
        global _warned_position
        if _warned_position or not os.environ.get("WAYLAND_DISPLAY"):
            return
        _warned_position = True
        if self.cfg["position"]["remember"] or self.cfg["position"]["anchor"]:
            log.info(
                "position.* is advisory: on Wayland the compositor places windows. "
                "Drag the widget to move it."
            )

    def update_now(self) -> None:
        """Sample data and refresh labels straight away."""
        self._tick()

    def _tick(self) -> bool:
        self.refresh()
        text = self.accessible_text()
        if text != self._last_text:
            self._last_text = text
            self.area.update_property([Gtk.AccessibleProperty.LABEL], [text])
            self.area.set_tooltip_text(text)
            self.area.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _on_close(self, *_: Any) -> bool:
        for timer in self._timers:
            GLib.source_remove(timer)
        self._timers.clear()
        return False

    def _on_draw(self, _area: Gtk.DrawingArea, cr: cairo.Context, w: int, h: int) -> None:
        c = self.cfg
        cr.set_operator(cairo.Operator.CLEAR)
        cr.paint()
        cr.set_operator(cairo.Operator.OVER)

        sh = c["shadow"]
        spread = sh["blur"] + max(abs(sh["offset_x"]), abs(sh["offset_y"]))
        inset = spread * self.scale if sh["enabled"] else 0.0
        inset += c["border"]["width"] * self.scale
        x, y = inset, inset
        bw, bh = w - 2 * inset, h - 2 * inset
        if bw <= 0 or bh <= 0:
            return
        kind = c["shape"]["kind"]
        radius = c["shape"]["radius"] * self.scale

        def path(dx: float = 0.0, dy: float = 0.0) -> None:
            shapes.shape_path(cr, kind, x + dx * self.scale, y + dy * self.scale, bw, bh, radius)

        if sh["enabled"]:
            shapes.drop_shadow(cr, path, {**sh, "blur": sh["blur"] * self.scale})

        alpha = c["opacity"]["background"]
        if kind == "ring":
            width = c["shape"]["ring_width"] * self.scale
            shapes.set_color(cr, c["colors"]["background"], alpha)
            shapes.ring(cr, x + bw / 2, y + bh / 2, (min(bw, bh) - width) / 2, width)
        else:
            shapes.fill_box(cr, path, c["colors"]["background"], alpha,
                            c["gradient"], (x, y, bw, bh))

        if c["border"]["width"] > 0:
            path()
            shapes.set_color(cr, c["border"]["color"])
            cr.set_line_width(c["border"]["width"] * self.scale)
            cr.stroke()

        pad_x, pad_y = (value * self.scale for value in theme.padding(c))
        if kind in ("circle", "ring", "diamond", "hexagon"):
            inner = (min(bw, bh) / 2) * (1 - math.sqrt(0.5))
            pad_x, pad_y = pad_x + inner, pad_y + inner
        self.draw(cr, x + pad_x, y + pad_y, bw - 2 * pad_x, bh - 2 * pad_y)
