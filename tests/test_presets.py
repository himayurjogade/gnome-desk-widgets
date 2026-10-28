"""Every shipped preset must be complete and meet WCAG AA."""

from __future__ import annotations

from pathlib import Path

import pytest

from desk_widgets import theme

CONFIG = Path(__file__).resolve().parent.parent / "config"
PRESETS = sorted(p.stem for p in (CONFIG / "presets").glob("*.toml"))


def test_presets_are_shipped():
    assert len(PRESETS) >= 14
    assert "catppuccin-mocha" in PRESETS and "high-contrast" in PRESETS


@pytest.mark.parametrize("name", PRESETS)
def test_preset_defines_every_core_colour(name):
    preset = theme.load_preset(name, CONFIG)
    assert set(theme.CORE_COLORS) <= set(preset["colors"])


@pytest.mark.parametrize("name", PRESETS)
@pytest.mark.parametrize("role", ["text", "muted", "accent"])
def test_preset_meets_wcag_aa(name, role):
    colors = theme.load_preset(name, CONFIG)["colors"]
    ratio = theme.contrast_ratio(colors[role], colors["background"])
    assert ratio >= theme.AA_CONTRAST, f"{name}: {role} is only {ratio:.2f}:1"


@pytest.mark.parametrize("name", PRESETS)
def test_preset_palettes_have_five_levels(name):
    for palette in theme.load_preset(name, CONFIG).get("palettes", {}).values():
        assert len(palette) == 5


def test_contrast_ratio_extremes():
    assert theme.contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert theme.contrast_ratio("#777777", "#777777") == pytest.approx(1.0)


def test_low_contrast_config_is_flagged(tmp_path, caplog):
    (tmp_path / "theme.toml").write_text(
        '[colors]\nbackground = "#1e1e2e"\ntext = "#242438"\n'
    )
    with caplog.at_level("WARNING"):
        theme.load("clock", tmp_path)
    assert any("WCAG AA" in message for message in caplog.messages)
