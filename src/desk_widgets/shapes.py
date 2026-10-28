"""Cairo and Pango drawing helpers shared by every widget."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo  # noqa: E402

from .theme import parse_color

Color = tuple[float, float, float, float]

WEIGHTS = {
    "thin": 100, "light": 300, "normal": 400, "regular": 400, "medium": 500,
    "semibold": 600, "bold": 700, "extrabold": 800, "heavy": 900,
}


def set_color(cr: cairo.Context, color: str | Color, alpha: float = 1.0) -> None:
    """Set the source to a hex string or RGBA tuple, scaled by ``alpha``."""
    r, g, b, a = parse_color(color) if isinstance(color, str) else color
    cr.set_source_rgba(r, g, b, a * alpha)


def rounded_rect(cr: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    """Append a rounded-rectangle path."""
    r = max(0.0, min(r, w / 2, h / 2))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def circle(cr: cairo.Context, cx: float, cy: float, r: float) -> None:
    """Append a circle path."""
    cr.new_sub_path()
    cr.arc(cx, cy, max(r, 0.0), 0, 2 * math.pi)
    cr.close_path()


def pill(cr: cairo.Context, x: float, y: float, w: float, h: float) -> None:
    """Append a fully rounded (pill) path."""
    rounded_rect(cr, x, y, w, h, min(w, h) / 2)


def ring(cr: cairo.Context, cx: float, cy: float, radius: float, width: float,
         fraction: float = 1.0, start: float = -math.pi / 2) -> None:
    """Stroke an arc covering ``fraction`` (0-1) of a ring. Call set_color first."""
    cr.set_line_width(width)
    cr.set_line_cap(cairo.LineCap.ROUND)
    cr.new_sub_path()
    cr.arc(cx, cy, radius, start, start + 2 * math.pi * max(0.0, min(fraction, 1.0)))
    cr.stroke()


def polygon(cr: cairo.Context, points: list[tuple[float, float]]) -> None:
    """Append a closed polygon path."""
    cr.new_sub_path()
    cr.move_to(*points[0])
    for point in points[1:]:
        cr.line_to(*point)
    cr.close_path()


def hexagon(cr: cairo.Context, x: float, y: float, w: float, h: float,
            flat: bool = True) -> None:
    """Append a hexagon path: flat-topped for windows, pointy for cells."""
    cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2, h / 2
    turn = 0.0 if flat else math.pi / 6
    polygon(cr, [
        (cx + rx * math.cos(turn + i * math.pi / 3),
         cy + ry * math.sin(turn + i * math.pi / 3))
        for i in range(6)
    ])


def diamond(cr: cairo.Context, x: float, y: float, w: float, h: float) -> None:
    """Append a diamond (rotated square) path."""
    polygon(cr, [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)])


def cut(cr: cairo.Context, x: float, y: float, w: float, h: float, size: float) -> None:
    """Append a rectangle with chamfered (cut) corners."""
    c = max(0.0, min(size, w / 2, h / 2))
    polygon(cr, [
        (x + c, y), (x + w - c, y), (x + w, y + c), (x + w, y + h - c),
        (x + w - c, y + h), (x + c, y + h), (x, y + h - c), (x, y + c),
    ])


def squircle(cr: cairo.Context, x: float, y: float, w: float, h: float,
             radius: float, smooth: float = 0.6) -> None:
    """Append a squircle: a rounded rectangle with continuous iOS-style corners."""
    r = max(0.0, min(radius * 1.6, w / 2, h / 2))
    k = r * (1 - max(0.0, min(smooth, 1.0)))
    cr.new_sub_path()
    cr.move_to(x + r, y)
    cr.line_to(x + w - r, y)
    cr.curve_to(x + w - k, y, x + w, y + k, x + w, y + r)
    cr.line_to(x + w, y + h - r)
    cr.curve_to(x + w, y + h - k, x + w - k, y + h, x + w - r, y + h)
    cr.line_to(x + r, y + h)
    cr.curve_to(x + k, y + h, x, y + h - k, x, y + h - r)
    cr.line_to(x, y + r)
    cr.curve_to(x, y + k, x + k, y, x + r, y)
    cr.close_path()


def dot(cr: cairo.Context, x: float, y: float, w: float, h: float) -> None:
    """Append a small centred dot, for sparse-looking grids."""
    circle(cr, x + w / 2, y + h / 2, min(w, h) * 0.3)


def bar(cr: cairo.Context, x: float, y: float, w: float, h: float) -> None:
    """Append a short horizontal bar, for a tally-style grid."""
    height = max(h * 0.45, 1.0)
    rounded_rect(cr, x, y + (h - height) / 2, w, height, height / 2)


def shape_path(cr: cairo.Context, kind: str, x: float, y: float, w: float, h: float,
               radius: float) -> None:
    """Append the window/cell outline for a shape kind from the config."""
    if kind == "circle":
        circle(cr, x + w / 2, y + h / 2, min(w, h) / 2)
    elif kind == "pill":
        pill(cr, x, y, w, h)
    elif kind == "square":
        cr.rectangle(x, y, w, h)
    elif kind == "squircle":
        squircle(cr, x, y, w, h, radius)
    elif kind == "hexagon":
        hexagon(cr, x, y, w, h, flat=w >= h)
    elif kind == "diamond":
        diamond(cr, x, y, w, h)
    elif kind == "cut":
        cut(cr, x, y, w, h, radius)
    elif kind == "dot":
        dot(cr, x, y, w, h)
    elif kind == "bar":
        bar(cr, x, y, w, h)
    else:  # rounded, and ring (which draws its outline as a rounded box)
        rounded_rect(cr, x, y, w, h, radius)


def gradient(x: float, y: float, w: float, h: float, start: str, end: str,
             angle: float) -> cairo.LinearGradient:
    """Two-stop linear gradient across the box, ``angle`` in degrees clockwise."""
    rad = math.radians(angle)
    dx, dy = math.cos(rad) * w / 2, math.sin(rad) * h / 2
    cx, cy = x + w / 2, y + h / 2
    grad = cairo.LinearGradient(cx - dx, cy - dy, cx + dx, cy + dy)
    grad.add_color_stop_rgba(0, *parse_color(start))
    grad.add_color_stop_rgba(1, *parse_color(end))
    return grad


def fill_box(cr: cairo.Context, path: Callable[[], None], color: str,
             alpha: float = 1.0, grad: dict[str, Any] | None = None,
             box: tuple[float, float, float, float] | None = None) -> None:
    """Fill a path with a flat colour, or with a gradient if one is enabled."""
    path()
    if grad and grad.get("enabled") and box:
        cr.save()
        cr.clip_preserve()
        cr.set_source(gradient(*box, grad["start"], grad["end"], grad.get("angle", 0.0)))
        cr.paint_with_alpha(alpha)
        cr.restore()
        cr.new_path()
    else:
        set_color(cr, color, alpha)
        cr.fill()


def drop_shadow(cr: cairo.Context, path: Callable[[float, float], None],
                shadow: dict[str, Any]) -> None:
    """Draw a soft shadow by stacking translucent offset copies of the path.

    ponytail: stacked strokes, not a real gaussian blur. Swap for a blurred
    ImageSurface if the fake edge ever shows.
    """
    layers = 6
    blur = max(shadow["blur"], 0.0)
    _, _, _, base_alpha = parse_color(shadow["color"])
    for i in range(layers, 0, -1):
        grow = blur * i / layers
        cr.save()
        path(shadow["offset_x"], shadow["offset_y"])
        set_color(cr, shadow["color"], base_alpha * 0.5 / layers)
        cr.set_line_width(grow * 2)
        cr.stroke()
        cr.restore()


def text_layout(cr: cairo.Context, text: str, font: dict[str, Any], family: str,
                scale: float = 1.0) -> Pango.Layout:
    """Build a Pango layout for ``text`` using a ``font.*`` config table."""
    layout = PangoCairo.create_layout(cr)
    # Grayscale AA: subpixel AA fringes on a translucent window background.
    opts = cairo.FontOptions()
    opts.set_antialias(cairo.Antialias.GRAY)
    PangoCairo.context_set_font_options(layout.get_context(), opts)
    desc = Pango.FontDescription()
    desc.set_family(family)
    desc.set_absolute_size(font["size"] * scale * Pango.SCALE)
    weight = str(font["weight"]).lower()
    numeric = int(weight) if weight.isdigit() else 400
    desc.set_weight(Pango.Weight(WEIGHTS.get(weight, numeric)))
    layout.set_font_description(desc)
    spacing = font.get("letter_spacing", 0.0)
    if spacing:
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_letter_spacing_new(int(spacing * Pango.SCALE)))
        layout.set_attributes(attrs)
    layout.set_text(text, -1)
    return layout


def draw_text(cr: cairo.Context, layout: Pango.Layout, x: float, y: float,
              color: str, align: str = "center", width: float = 0.0) -> float:
    """Draw a layout at ``y``, aligned inside ``width``. Returns its height."""
    tw, th = (d / Pango.SCALE for d in layout.get_size())
    if align == "center":
        x += (width - tw) / 2
    elif align == "end":
        x += width - tw
    set_color(cr, color)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)
    return th
