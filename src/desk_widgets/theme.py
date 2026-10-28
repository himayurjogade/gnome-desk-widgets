"""Theme loading: defaults -> preset -> theme.toml -> widgets/<name>.toml.

Pure config handling, no GTK imports, so it is unit-testable.
"""

from __future__ import annotations

import logging
import os
import re
import tomllib
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

PKG_DIR = Path(__file__).resolve().parent
BUNDLED_CONFIG = PKG_DIR.parent.parent / "config"

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

#: Keys (by dotted path) whose string values must be colors.
COLOR_SECTIONS = ("colors", "gradient", "border", "shadow")

#: Allowed values for enum-ish options, by dotted path.
ENUMS: dict[str, set[str]] = {
    "shape.kind": {"rounded", "square", "circle", "pill", "ring", "squircle", "hexagon",
                   "diamond", "cut"},
    "shape.cell": {"square", "circle", "rounded", "diamond", "hexagon", "dot", "bar", "pill"},
    "position.anchor": {"top-left", "top-right", "bottom-left", "bottom-right", "center"},
    "behavior.week_start": {"monday", "sunday"},
    "clock.style": {"plain", "boxed", "split"},
    "system.style": {"bar", "ring", "number"},
    "layout.align": {"center", "start", "end"},
    "layout.title_align": {"", "center", "start", "end"},
    "layout.value_align": {"", "center", "start", "end"},
    "layout.direction": {"vertical", "horizontal"},
}

#: Numeric ranges, by dotted path.
CLAMPS: dict[str, tuple[float, float]] = {
    "opacity.background": (0.0, 1.0),
    "size.scale": (0.25, 4.0),
    "size.width": (40, 4000),
    "size.height": (40, 4000),
    "behavior.grid_weeks": (1, 53),
    "behavior.stats_interval": (0.2, 3600),
    "behavior.remote_interval": (30, 86400),
}

DEFAULTS: dict[str, Any] = {
    "preset": "catppuccin-mocha",
    "preset_light": "catppuccin-latte",
    "follow_system": False,
    "size": {"width": 320, "height": 150, "scale": 1.0},
    "position": {
        "anchor": "top-right",
        "margin_x": 32,
        "margin_y": 32,
        "monitor": 0,
        "remember": True,
    },
    "shape": {
        "kind": "rounded",
        "radius": 20.0,
        "ring_width": 12.0,
        "cell": "rounded",
        "cell_radius": 2.0,
        "cell_size": 11.0,
        "cell_gap": 3.0,
    },
    "colors": {
        "background": "#1e1e2e",
        "text": "#cdd6f4",
        "muted": "#a6adc8",
        "accent": "#89b4fa",
        "track": "#313244",
        "border": "#45475a",
        "shadow": "#000000",
        # Per-element overrides. Empty means "inherit", see INHERITS.
        "title": "",
        "value": "",
        "date": "",
        "legend": "",
        "label": "",
        "hover": "",
        "grid_empty": "",
        "grid_border": "",
    },
    "opacity": {"background": 0.88},
    "gradient": {"enabled": False, "start": "#1e1e2e", "end": "#313244", "angle": 135.0},
    "bar_gradient": {"enabled": False, "start": "#89b4fa", "end": "#f5c2e7", "angle": 0.0},
    "border": {"width": 0.0, "color": "#45475a"},
    "shadow": {"enabled": True, "blur": 18.0, "offset_x": 0.0, "offset_y": 4.0,
               "color": "#00000099"},
    "font": {
        "family": "JetBrains Mono",
        "title": {"size": 13.0, "weight": "bold", "letter_spacing": 1.5},
        "value": {"size": 46.0, "weight": "bold", "letter_spacing": 0.0},
        "small": {"size": 12.0, "weight": "normal", "letter_spacing": 0.0},
        "date": {"size": 12.0, "weight": "normal", "letter_spacing": 0.0},
        "legend": {"size": 10.0, "weight": "normal", "letter_spacing": 0.0},
    },
    "layout": {
        "padding": 20.0,
        "spacing": 6.0,
        "align": "center",
        "padding_x": 0.0,  # 0 = use padding
        "padding_y": 0.0,
        "title_align": "",  # empty = use align
        "value_align": "",
        "direction": "vertical",
        "order": ["title", "value", "date", "grid", "legend"],
    },
    "show": {
        "title": True,
        "value": True,
        "date": True,
        "seconds": False,
        "grid": True,
        "legend": True,
        "longest_streak": True,
    },
    "behavior": {
        "stats_interval": 2.0,
        "remote_interval": 900.0,
        "grid_weeks": 26,
        "week_start": "sunday",
        "reduced_motion": False,
        "text_scaling": True,
    },
    "palettes": {
        "github": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "leetcode": ["#2b2b2b", "#2f4f3a", "#3c6e47", "#ffa116", "#ffc53d"],
    },
}

#: Extra tables that only exist for one widget.
WIDGET_DEFAULTS: dict[str, dict[str, Any]] = {
    "clock": {
        "clock": {
            "style": "plain",
            "time_format": "%H:%M",
            "seconds_format": "%H:%M:%S",
            "date_format": "%A, %d %B",
            "title": "CLOCK",
        }
    },
    "system": {
        "system": {
            "metrics": ["cpu", "ram", "disk"],
            "style": "bar",
            "disk_path": "/",
            "bar_height": 10.0,
            "ring_size": 54.0,
            "title": "SYSTEM",
            "labels": {"cpu": "CPU", "ram": "RAM", "disk": "DISK"},
        }
    },
    "github": {
        "github": {
            "username": "octocat",
            "palette": "github",
            "title": "GITHUB",
            "timeout": 8.0,
        }
    },
    "leetcode": {
        "leetcode": {
            "username": "leetcode",
            "palette": "leetcode",
            "title": "LEETCODE",
            "timeout": 8.0,
            "levels": [1, 3, 6, 10],
        }
    },
}


def merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``over`` onto ``base``, returning a new dict."""
    out = dict(base)
    for key, value in over.items():
        cur = out.get(key)
        if isinstance(cur, dict) and isinstance(value, dict):
            out[key] = merge(cur, value)
        else:
            out[key] = value
    return out


def parse_color(value: str) -> tuple[float, float, float, float]:
    """Parse ``#rgb``/``#rgba``/``#rrggbb``/``#rrggbbaa`` into RGBA floats."""
    text = value.lstrip("#")
    if len(text) in (3, 4):
        text = "".join(ch * 2 for ch in text)
    if len(text) == 6:
        text += "ff"
    nums = [int(text[i : i + 2], 16) / 255 for i in range(0, 8, 2)]
    return nums[0], nums[1], nums[2], nums[3]


#: Colours every preset must define; the rest inherit from these.
CORE_COLORS = ("background", "text", "muted", "accent", "track", "border", "shadow")

#: Which colour each per-element override falls back to when left empty.
INHERITS = {
    "title": "accent",
    "value": "text",
    "date": "muted",
    "legend": "muted",
    "label": "muted",
    "hover": "text",
    "grid_empty": "track",
    "grid_border": "",
}


def color(cfg: dict[str, Any], role: str) -> str:
    """Resolve a colour role, following the inherit chain. ``""`` means none."""
    colors = cfg["colors"]
    chosen = colors.get(role, "")
    if chosen:
        return chosen
    fallback = INHERITS.get(role, role)
    return colors.get(fallback, "") if fallback else ""


def align(cfg: dict[str, Any], element: str = "") -> str:
    """Alignment for one element, falling back to ``layout.align``."""
    return cfg["layout"].get(f"{element}_align") or cfg["layout"]["align"]


def padding(cfg: dict[str, Any]) -> tuple[float, float]:
    """Horizontal and vertical padding, each falling back to ``layout.padding``."""
    layout = cfg["layout"]
    return (layout["padding_x"] or layout["padding"], layout["padding_y"] or layout["padding"])


def ordered(cfg: dict[str, Any], available: set[str]) -> list[str]:
    """The configured element order, limited to what this widget can draw."""
    return [name for name in cfg["layout"]["order"] if name in available]


def _relative_luminance(color_hex: str) -> float:
    """WCAG relative luminance of a colour."""
    channels = []
    for value in parse_color(color_hex)[:3]:
        channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two colours, 1.0 (none) to 21.0 (black/white)."""
    first, second = _relative_luminance(foreground), _relative_luminance(background)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


#: WCAG AA minimum for normal text.
AA_CONTRAST = 4.5


def check_contrast(cfg: dict[str, Any]) -> list[str]:
    """Warn about text colours that fail WCAG AA against the background."""
    background = cfg["colors"]["background"]
    failures = []
    for role in ("text", "muted", "accent", "title", "value", "date", "legend", "label"):
        chosen = color(cfg, role)
        if chosen and contrast_ratio(chosen, background) < AA_CONTRAST:
            failures.append(role)
            log.warning(
                "config: colors.%s (%s) has %.1f:1 contrast on the background, "
                "below the WCAG AA minimum of %.1f:1",
                role, chosen, contrast_ratio(chosen, background), AA_CONTRAST,
            )
    return failures


def _is_color_path(path: str) -> bool:
    head = path.split(".")[0]
    return head in COLOR_SECTIONS or path.endswith(("color", "_color"))


def _validate(node: Any, defaults: dict[str, Any], path: str = "") -> dict[str, Any]:
    """Return ``node`` filtered to the shape of ``defaults``, warning on junk."""
    if not isinstance(node, dict):
        log.warning("config: %s should be a table, using defaults", path or "<root>")
        return dict(defaults)

    out: dict[str, Any] = {}
    for key, default in defaults.items():
        dotted = f"{path}.{key}" if path else key
        if key not in node:
            out[key] = dict(default) if isinstance(default, dict) else default
            continue
        value = node[key]

        if isinstance(default, dict):
            out[key] = _validate(value, default, dotted)
            continue

        reported = False
        if isinstance(default, bool):
            ok = isinstance(value, bool)
        elif isinstance(default, (int, float)):
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        elif isinstance(default, list):
            ok = isinstance(value, list) and bool(value)
            if ok and all(_HEX.match(str(v)) for v in default):
                ok = all(isinstance(v, str) and _HEX.match(v) for v in value)
            elif ok:
                ok = all(isinstance(v, type(default[0])) for v in value)
        else:
            ok = isinstance(value, str)
            if ok and dotted in ENUMS and value not in ENUMS[dotted]:
                log.warning(
                    "config: %s = %r is not one of %s, using %r",
                    dotted, value, sorted(ENUMS[dotted]), default,
                )
                ok, reported = False, True
            if ok and value and _is_color_path(dotted) and not _HEX.match(value):
                log.warning("config: %s = %r is not a hex color, using %r",
                            dotted, value, default)
                ok, reported = False, True

        if not ok:
            if not reported:
                log.warning("config: %s = %r has the wrong type, using %r",
                            dotted, value, default)
            value = default
        if dotted in CLAMPS:
            low, high = CLAMPS[dotted]
            if not low <= value <= high:
                log.warning("config: %s = %r outside %s-%s, clamped", dotted, value, low, high)
                value = min(max(value, low), high)
        out[key] = value

    for key in node.keys() - defaults.keys():
        log.warning("config: unknown option %s, ignored", f"{path}.{key}" if path else key)
    return out


def _validate_all(cfg: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Validate ``cfg``, treating ``palettes`` as free-form lists of colors."""
    palettes = cfg.get("palettes")
    strip = lambda d: {k: v for k, v in d.items() if k != "palettes"}  # noqa: E731
    out = _validate(strip(cfg), strip(defaults))
    out["palettes"] = dict(defaults.get("palettes", {}))
    if isinstance(palettes, dict):
        for name, colors in palettes.items():
            if isinstance(colors, list) and colors and all(_HEX.match(str(c)) for c in colors):
                out["palettes"][name] = [str(c) for c in colors]
            else:
                log.warning("config: palettes.%s is not a list of hex colors, ignored", name)
    elif palettes is not None:
        log.warning("config: palettes should be a table, ignored")
    return out


def config_dir() -> Path:
    """Config directory: ``$DESK_WIDGETS_CONFIG``, the user's, or the bundled one."""
    env = os.environ.get("DESK_WIDGETS_CONFIG")
    if env:
        return Path(env).expanduser()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    user = xdg / "desk-widgets"
    return user if (user / "theme.toml").exists() else BUNDLED_CONFIG


def _read_toml(path: Path) -> dict[str, Any]:
    """Read a TOML file, returning ``{}`` if it is missing or broken."""
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        return {}
    except (tomllib.TOMLDecodeError, OSError) as exc:
        log.warning("config: cannot read %s (%s), using defaults", path, exc)
        return {}


def pick_preset(theme: dict[str, Any], widget_cfg: dict[str, Any],
                scheme: str | None = None) -> str | None:
    """Choose the dark or light preset, honouring ``follow_system``."""
    def option(key: str) -> Any:
        return widget_cfg.get(key, theme.get(key, DEFAULTS[key]))

    if option("follow_system") and scheme == "light":
        return option("preset_light") or option("preset")
    return option("preset")


def load(widget: str, directory: Path | None = None,
         scheme: str | None = None) -> dict[str, Any]:
    """Load the merged, validated config for one widget.

    ``scheme`` is "light" or "dark"; with ``follow_system`` it picks which
    preset to load.
    """
    root = directory or config_dir()
    defaults = merge(DEFAULTS, WIDGET_DEFAULTS.get(widget, {}))
    theme = _read_toml(root / "theme.toml")
    widget_cfg = _read_toml(root / "widgets" / f"{widget}.toml")

    cfg = merge(defaults, load_preset(pick_preset(theme, widget_cfg, scheme), root))
    cfg = merge(cfg, merge(theme, widget_cfg))
    cfg = _validate_all(cfg, defaults)
    check_contrast(cfg)
    cfg["_widget"] = widget
    return cfg


def load_preset(name: str | None, root: Path | None = None) -> dict[str, Any]:
    """Load ``presets/<name>.toml`` (colors and palettes only)."""
    if not name:
        return {}
    for base in (root or config_dir(), BUNDLED_CONFIG):
        path = base / "presets" / f"{name}.toml"
        if path.exists():
            return _read_toml(path)
    log.warning("config: preset %r not found, keeping default colors", name)
    return {}
