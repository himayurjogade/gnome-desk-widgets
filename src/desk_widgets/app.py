"""Launcher: ``desk-widgets [clock|all|reload|list]``."""

from __future__ import annotations

import logging
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import theme
from .widgets.base import BaseWidget
from .widgets.clock import ClockWidget
from .widgets.github import GitHubWidget
from .widgets.leetcode import LeetCodeWidget
from .widgets.system import SystemWidget

log = logging.getLogger("desk_widgets")

#: Available widgets, by command-line name.
WIDGETS: dict[str, type[BaseWidget]] = {
    "clock": ClockWidget,
    "system": SystemWidget,
    "github": GitHubWidget,
    "leetcode": LeetCodeWidget,
}

USAGE = f"""usage: desk-widgets [{'|'.join(WIDGETS)}|all|reload|list]

  <name>   open one widget
  all      open every widget
  reload   re-read the config in the running instance
  list     print the available widgets
"""


INTERFACE_SCHEMA = "org.gnome.desktop.interface"


def desktop_settings() -> Gio.Settings | None:
    """The GNOME interface settings, or None when the schema is not installed."""
    source = Gio.SettingsSchemaSource.get_default()
    if source is None or source.lookup(INTERFACE_SCHEMA, True) is None:
        return None
    return Gio.Settings.new(INTERFACE_SCHEMA)


def system_scheme(settings: Gio.Settings | None = None) -> str:
    """"dark" or "light", from the desktop colour-scheme preference."""
    settings = settings or desktop_settings()
    if settings is None:
        return "dark"
    try:
        return "dark" if settings.get_string("color-scheme") == "prefer-dark" else "light"
    except GLib.Error:  # pragma: no cover - schema without the key
        return "dark"


class App(Gtk.Application):
    """One process owning every open widget window."""

    def __init__(self) -> None:
        super().__init__(
            application_id="io.github.himayurjogade.DeskWidgets",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.open: dict[str, BaseWidget] = {}
        self.settings = desktop_settings()
        self.scheme = system_scheme(self.settings)
        if self.settings is not None:
            self.settings.connect("changed::color-scheme", self._on_scheme_changed)

    def show(self, name: str) -> None:
        """Open a widget, replacing it if it is already open."""
        if old := self.open.pop(name, None):
            old.close()  # close-request stops its timers
        window = WIDGETS[name](self, theme.load(name, scheme=self.scheme))
        self.open[name] = window
        window.update_now()
        window.present()

    def _on_scheme_changed(self, settings: Gio.Settings, _key: str) -> None:
        """Re-theme every open widget when the desktop switches light/dark."""
        scheme = system_scheme(settings)
        if scheme == self.scheme:
            return
        self.scheme = scheme
        log.info("desktop switched to %s, re-theming widgets", scheme)
        for name in list(self.open):
            self.show(name)

    def do_command_line(self, cmdline: Gio.ApplicationCommandLine) -> int:  # noqa: N802
        """Handle a launch, routed by D-Bus to the already-running instance."""
        args: list[str] = cmdline.get_arguments()[1:] or ["all"]
        cmd = args[0]

        if cmd in ("-h", "--help", "help"):
            cmdline.print_literal(USAGE)
            return 0
        if cmd == "list":
            cmdline.print_literal("\n".join(WIDGETS) + "\n")
            return 0
        if cmd == "reload":
            if not self.open:
                cmdline.print_literal("nothing running\n")
                return 1
            for name in list(self.open):
                self.show(name)
            return 0

        names = list(WIDGETS) if cmd == "all" else [a for a in args if a in WIDGETS]
        unknown = [a for a in args if a not in WIDGETS and a != "all"]
        if unknown:
            cmdline.print_literal(f"unknown widget: {', '.join(unknown)}\n{USAGE}")
            return 2
        for name in names:
            self.show(name)
        return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    return App().run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
