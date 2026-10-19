"""Settings — desktop settings, Dev Mode unlock, about."""
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .. import config
from . import base
from .base import button, row_label

SECRET_PASSWORD = "double-double"


def build(win, opts=None):
    return Settings(win)


class Settings(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("app-root")
        self.win = win

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        stack = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        stack.set_valign(Gtk.Align.START)
        stack.set_margin_top(10)
        stack.set_margin_bottom(10)
        stack.set_margin_start(16)
        stack.set_margin_end(16)
        scroll.set_child(stack)

        # --- About -----------------------------------------------
        about = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        about.append(row_label("CanadaOS 1.0", "app-title"))
        about.append(row_label(
            "A graphical Debian live desktop.\n"
            "Debian live-build · Python/GTK4 · fits on one CD.",
            "muted-label"))
        stack.append(about)

        # --- Appearance ------------------------------------------
        self.wallpaper_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.wallpaper_box.append(row_label("Wallpaper", "section-title"))
        self.wallpaper_rows = []
        for value, pretty in config.WALLPAPERS:
            btn = button(("●  " if config.wallpaper() == value else "○  ") + pretty,
                         (lambda v=value: (lambda *_: self.set_wallpaper(v)))(),
                         "app-tile")
            button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            button_row.append(btn)
            self.wallpaper_rows.append((value, btn))
            self.wallpaper_box.append(button_row)
        stack.append(self.wallpaper_box)

        # --- Dev Mode --------------------------------------------
        dev = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        dev.append(row_label("Developer Mode", "section-title"))

        self.state_label = row_label(self._state_text(), "muted-label")
        self.state_label.set_wrap(True)
        dev.append(self.state_label)

        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.entry = Gtk.Entry()
        self.entry.set_hexpand(True)
        self.entry.set_visibility(False)
        self.entry.set_placeholder_text("Unlock password")
        self.entry.connect("activate", lambda *_: self.try_unlock())
        entry_row.append(self.entry)
        entry_row.append(button("Unlock 🔓", lambda *_: self.try_unlock()))
        entry_row.append(button("Turn off", lambda *_: self.disable_dev()))
        dev.append(entry_row)

        hint = row_label(
            "Hint: a Tim Hortons coffee order with two creams and two sugars.",
            "muted-label")
        hint.set_wrap(True)
        dev.append(hint)
        stack.append(dev)

        # --- Paths for the curious -------------------------------
        paths = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        paths.append(row_label("Where things live", "section-title"))
        paths.append(row_label(
            "Shell: /usr/bin/canadaos-shell\n"
            "Terminal config: /etc/canadaos/sorryrc\n"
            "Extras: /usr/local/bin/{sorry, hockey, poursyrup, toque, beaver}",
            "muted-label"))
        stack.append(paths)

        header = row_label("Settings", "app-title")
        header.set_margin_start(16)
        header.set_margin_top(12)
        self.append(header)
        self.append(scroll)

    @staticmethod
    def _state_text():
        if config.is_dev_mode():
            return ("Developer Mode is ON — Sorry Terminal and the Maple Syrup editor "
                    "are unlocked.")
        return ("Developer Mode is OFF. Unlock to add the terminal and the .maple editor "
                "to the dock.")

    def set_wallpaper(self, value):
        config.set_key("wallpaper", value)
        self.win.desktop.set_wallpaper(value)
        for w_value, btn in self.wallpaper_rows:
            text = btn.get_label() or ""
            mark = "●" if w_value == value else "○"
            btn.set_label(mark + "  " + text.split("  ", 1)[-1])

    def try_unlock(self):
        guess = self.entry.get_text().strip().lower().replace(" ", "")
        accepted = {SECRET_PASSWORD, SECRET_PASSWORD.replace("-", "")}
        if guess in accepted:
            config.set_key("dev_mode", True)
            self.state_label.set_text(self._state_text())
            self.entry.set_text("")
            # refresh + feedback FIRST so a dialog problem can never swallow
            # the whole unlock (that's how the dock kept showing locks before).
            self.win.desktop.refresh_dock()
            self.win.desktop.refresh_apps()
            self.win.desktop.show_toast("Developer Mode unlocked 🍁")
            base.info_dialog(self.win, "Unlocked",
                             "Developer Mode is on.\n"
                             "New in the dock: 💻 Sorry Terminal and 🍁 Maple Syrup editor.")
        else:
            self.entry.set_text("")
            base.info_dialog(self.win, "Not quite",
                             "Wrong password.\nHint: coffee order, two creams, two sugars.")

    def disable_dev(self):
        config.set_key("dev_mode", False)
        self.state_label.set_text(self._state_text())
        self.win.desktop.refresh_dock()
        self.win.desktop.refresh_apps()
        self.win.desktop.show_toast("Developer Mode off 🍁")
