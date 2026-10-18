"""CanadaOS entry point: python3 -m canadaos.main"""
import sys
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio

from .desktop import DesktopWindow

BASE_DIR = Path(__file__).resolve().parent


def apply_theme():
    try:
        Gtk.StyleManager.get_default().set_color_scheme(Gtk.ColorScheme.FORCE_DARK)
    except (AttributeError, TypeError):
        pass  # older GTK is already dark-ish with our CSS, eh

    provider = Gtk.CssProvider()
    css_path = BASE_DIR / "data" / "canada.css"
    try:
        provider.load_from_path(str(css_path))
    except Exception:
        # inline fallback so the OS never boots ugly
        provider.load_from_data(
            b".canada-root { background: #101418; color: #e8edf2; }")
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class CanadaApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="ca.canadaos.Shell",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_startup(self):
        self.hold()
        Gtk.Application.do_startup(self)
        apply_theme()

    def do_activate(self):
        self.window = DesktopWindow(self)
        self.window.present()


def main():
    CanadaApp().run(sys.argv)


if __name__ == "__main__":
    main()
