"""Theme merging, validation and preset loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from desk_widgets import theme

CONFIG = Path(__file__).resolve().parent.parent / "config"


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_merge_is_recursive_and_non_destructive():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    over = {"a": {"y": 9}}
    assert theme.merge(base, over) == {"a": {"x": 1, "y": 9}, "b": 3}
    assert base["a"]["y"] == 2


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("#fff", (1.0, 1.0, 1.0, 1.0)),
        ("#000000", (0.0, 0.0, 0.0, 1.0)),
        ("#ff000080", (1.0, 0.0, 0.0, 128 / 255)),
    ],
)
def test_parse_color(text, expected):
    assert theme.parse_color(text) == pytest.approx(expected)


def test_defaults_when_config_missing(tmp_path):
    cfg = theme.load("clock", tmp_path)
    assert cfg["size"]["width"] == theme.DEFAULTS["size"]["width"]
    assert cfg["clock"]["style"] == "plain"


def test_widget_overrides_beat_global_theme(tmp_path):
    write(tmp_path, "theme.toml", '[size]\nwidth = 200\nheight = 100\n')
    write(tmp_path, "widgets/clock.toml", '[size]\nwidth = 400\n')
    cfg = theme.load("clock", tmp_path)
    assert cfg["size"]["width"] == 400
    assert cfg["size"]["height"] == 100


def test_preset_supplies_colors_but_theme_wins(tmp_path):
    write(tmp_path, "theme.toml", 'preset = "nord"\n[colors]\ntext = "#123456"\n')
    write(tmp_path, "presets/nord.toml", '[colors]\nbackground = "#2e3440"\ntext = "#eceff4"\n')
    cfg = theme.load("clock", tmp_path)
    assert cfg["colors"]["background"] == "#2e3440"
    assert cfg["colors"]["text"] == "#123456"


def test_bad_values_fall_back_with_a_warning(tmp_path, caplog):
    write(
        tmp_path,
        "theme.toml",
        '[size]\nwidth = "wide"\n[shape]\nkind = "triangle"\n'
        '[colors]\naccent = "blurple"\n[opacity]\nbackground = 5.0\n[nope]\nx = 1\n',
    )
    with caplog.at_level("WARNING"):
        cfg = theme.load("clock", tmp_path)
    assert cfg["size"]["width"] == theme.DEFAULTS["size"]["width"]
    assert cfg["shape"]["kind"] == "rounded"
    assert cfg["colors"]["accent"] == theme.DEFAULTS["colors"]["accent"]
    assert cfg["opacity"]["background"] == 1.0  # clamped
    messages = " ".join(caplog.messages)
    for fragment in ("size.width", "shape.kind", "colors.accent", "opacity.background", "nope"):
        assert fragment in messages


def test_palettes_accept_custom_names_and_reject_junk(tmp_path, caplog):
    write(tmp_path, "theme.toml", '[palettes]\nmine = ["#000", "#fff"]\nbroken = ["nope"]\n')
    with caplog.at_level("WARNING"):
        cfg = theme.load("clock", tmp_path)
    assert cfg["palettes"]["mine"] == ["#000", "#fff"]
    assert "broken" not in cfg["palettes"]
    # untouched palettes keep the active preset's colours
    assert cfg["palettes"]["github"] == theme.load_preset("catppuccin-mocha", CONFIG)[
        "palettes"]["github"]


def test_booleans_are_not_numbers(tmp_path, caplog):
    write(tmp_path, "theme.toml", '[size]\nscale = true\n[show]\ntitle = 1\n')
    with caplog.at_level("WARNING"):
        cfg = theme.load("clock", tmp_path)
    assert cfg["size"]["scale"] == theme.DEFAULTS["size"]["scale"]
    assert cfg["show"]["title"] is True  # default, not the int


@pytest.mark.parametrize("name", ["catppuccin-mocha", "tokyo-night", "gruvbox", "nord",
                                  "dracula", "high-contrast"])
def test_shipped_presets_define_every_colour(name):
    preset = theme.load_preset(name, CONFIG)
    assert set(theme.CORE_COLORS) <= set(preset["colors"])


def test_missing_preset_keeps_defaults(caplog):
    with caplog.at_level("WARNING"):
        assert theme.load_preset("does-not-exist", CONFIG) == {}
    assert "does-not-exist" in " ".join(caplog.messages)


def test_one_warning_per_bad_option(tmp_path, caplog):
    write(tmp_path, "theme.toml", '[layout]\nalign = "middle"\n')
    with caplog.at_level("WARNING"):
        cfg = theme.load("clock", tmp_path)
    assert cfg["layout"]["align"] == "center"
    assert len([m for m in caplog.messages if "layout.align" in m]) == 1


def test_default_preset_applies_without_being_named(tmp_path):
    write(tmp_path, "theme.toml", "[size]\nwidth = 200\n")
    assert theme.load("clock", tmp_path)["colors"]["background"] == "#1e1e2e"


def test_follow_system_swaps_in_the_light_preset(tmp_path):
    write(tmp_path, "theme.toml",
          'preset = "nord"\npreset_light = "day"\nfollow_system = true\n')
    write(tmp_path, "presets/nord.toml", '[colors]\nbackground = "#2e3440"\n')
    write(tmp_path, "presets/day.toml", '[colors]\nbackground = "#ffffff"\n')
    assert theme.load("clock", tmp_path, "dark")["colors"]["background"] == "#2e3440"
    assert theme.load("clock", tmp_path, "light")["colors"]["background"] == "#ffffff"


def test_follow_system_off_keeps_the_dark_preset(tmp_path):
    write(tmp_path, "theme.toml", 'preset = "nord"\npreset_light = "day"\n')
    write(tmp_path, "presets/nord.toml", '[colors]\nbackground = "#2e3440"\n')
    write(tmp_path, "presets/day.toml", '[colors]\nbackground = "#ffffff"\n')
    assert theme.load("clock", tmp_path, "light")["colors"]["background"] == "#2e3440"


@pytest.mark.parametrize(
    ("role", "expected"),
    [("title", "accent"), ("value", "text"), ("date", "muted"),
     ("legend", "muted"), ("hover", "text"), ("grid_empty", "track")],
)
def test_colour_roles_inherit_when_empty(role, expected):
    cfg = theme.load("clock", CONFIG)
    assert theme.color(cfg, role) == cfg["colors"][expected]


def test_colour_role_override_wins(tmp_path):
    write(tmp_path, "theme.toml", '[colors]\ntitle = "#ff00ff"\n')
    cfg = theme.load("clock", tmp_path)
    assert theme.color(cfg, "title") == "#ff00ff"
    assert theme.color(cfg, "value") == cfg["colors"]["text"]


def test_grid_border_is_none_by_default():
    assert theme.color(theme.load("github", CONFIG), "grid_border") == ""


def test_empty_colour_is_not_a_bad_value(tmp_path, caplog):
    write(tmp_path, "theme.toml", '[colors]\ntitle = ""\n')
    with caplog.at_level("WARNING"):
        theme.load("clock", tmp_path)
    assert not [m for m in caplog.messages if "colors.title" in m]


def test_every_option_is_consumed_somewhere():
    """No option may be validated but ignored: the schema file does not count."""
    src = "\n".join(
        path.read_text()
        for path in (CONFIG.parent / "src").rglob("*.py")
        if path.name != "theme.py"
    )
    defaults = theme.DEFAULTS
    for extra in theme.WIDGET_DEFAULTS.values():
        defaults = theme.merge(defaults, extra)

    def leaves(node, prefix=""):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                yield from leaves(value, path)
            else:
                yield path, key

    # Options reached through a theme.py helper (color/align/padding/ordered/pick_preset).
    via_helper = {
        "preset", "preset_light", "follow_system", "colors.text", "colors.muted",
        "layout.align", "layout.padding_x", "layout.padding_y",
        "layout.title_align", "layout.value_align", "layout.order",
    }
    # Parsed and validated, but the compositor owns window placement on Wayland.
    advisory = {"position.margin_x", "position.margin_y", "position.monitor"}
    dead = [
        path for path, key in leaves(defaults)
        if f'"{key}"' not in src and path not in via_helper | advisory
    ]
    assert dead == [], f"options nothing reads: {dead}"
