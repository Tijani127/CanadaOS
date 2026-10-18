"""Sorry Terminal — real bash via VTE, wrapped in Canadian politeness. Dev Mode only."""
import os

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from . import base
from .base import app_root, button, row_label

PALETTE_DARK = [
    "#10141a",  # background placeholder (slot 0 handled separately)
    "#d52b1e", "#7ec142", "#e9b44c", "#5db6d7", "#c792ea", "#3fc4a4", "#e8edf2",
    "#5c6670", "#ff6f61", "#9bd56d", "#ffd580", "#8ecbea", "#dda3ef", "#6fdcc6", "#ffffff",
]


def _load_vte():
    import importlib
    for ver in ("3.91",):
        try:
            import gi as _gi
            _gi.require_version("Vte", ver)
            return importlib.import_module("gi.repository.Vte")
        except (ValueError, TypeError, ImportError):
            pass
    return None


class Terminal(Gtk.Box):
    def __init__(self, win, opts=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("app-root")
        self.win = win

        self._vte = _load_vte()
        if self._vte is None:
            self._fallback()
            return

        term = self._vte.Terminal()
        self._apply_colors(term)

        argv = self._shell_argv()
        from gi.repository import GLib
        term.spawn_async(
            self._vte.PtyFlags.DEFAULT,
            os.path.expanduser("~"),
            argv, ["CANADAOS=1", "TERM=xterm-256color"],
            GLib.SpawnFlags.DEFAULT,
            None, None, None, None, None, None,
        )

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(term)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.append(button("New shell", lambda *_: self.win.desktop.launch("terminal")))
        bar.append(row_label("Real bash. Easter eggs: sorry · hockey · poursyrup · toque · timmy", "muted-label"))

        self.append(bar)
        self.append(scroller)

    def _shell_argv(self):
        wrapper = "/usr/local/bin/sorry-shell"
        if os.access(wrapper, os.X_OK):
            return [wrapper]
        return ["/bin/bash", "-l"]

    def _apply_colors(self, term):
        from gi.repository import Gdk
        def rgba(s):
            c = Gdk.RGBA()
            c.parse(s)
            return c
        bg = rgba("#10141a")
        fg = rgba("#e8edf2")
        palette = [rgba(c) for c in PALETTE_DARK[1:]]
        try:
            term.set_colors(fg, bg, palette)
        except Exception:
            pass

    def _fallback(self):
        box = app_root(spacing=10)
        box.set_valign(Gtk.Align.CENTER)
        box.append(row_label("💻 VTE binding not found.", "app-title"))
        box.append(row_label("On the Debian image run:\n"
                             "  sudo apt install gir1.2-vte-3.91", "muted-label"))
        box.append(button("Try Settings", lambda *_: self.win.desktop.launch("settings")))
        self.append(box)

    def build(self):
        return self


def build(win, opts=None):
    return Terminal(win, opts=opts)
