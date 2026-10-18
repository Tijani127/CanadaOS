"""Settings — theme, Dev Mode unlock (secret password), about."""
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .. import config
from . import base
from .base import app_root, button, row_label

SECRET_PASSWORD = "double-double"


def build(win, opts=None):
    return Settings(win)


class Settings(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add_css_class("app-root")
        self.win = win

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        stack = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        stack.set_valign(Gtk.Align.START)
        stack.set_margin_top(8)
        stack.set_margin_bottom(8)
        stack.set_margin_start(12)
        stack.set_margin_end(12)
        scroll.set_child(stack)

        # --- About ---
        about = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        about.append(row_label("🍁 CanadaOS 1.0 'Double-Double'", "app-title"))
        about.append(row_label(
            "Powered by Debian live-build + Python/GTK4. Politeness: maxed out.\n"
            "Current wallpaper: {}".format(config.wallpaper().title().replace('-', ' ')),
            "muted-label"))
        stack.append(about)

        # --- Wallpaper ---
        wallpaper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        wallpaper.append(row_label("Wallpapers", "section-title"))
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for value, pretty in config.WALLPAPERS:
            label = pretty + (" 🟢" if config.wallpaper() == value else "")
            btn = button(label,
                         (lambda v=value: (lambda *_: self.set_wallpaper(v)))(),
                         "app-tile")
            row.append(btn)
        wallpaper.append(row)
        stack.append(wallpaper)

        # --- Dev Mode ---
        dev = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        dev.append(row_label("Dev Mode 🍁", "section-title"))
        self.state_label = row_label(
            "Dev Mode is ON. Sorry Terminal + Maple Syrup editor unlocked, eh!"
            if config.is_dev_mode() else
            "Dev Mode is OFF. Unlock for: 💻 Sorry Terminal, 🍁 Maple Syrup editor.",
            "muted-label")
        dev.append(self.state_label)

        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.entry = Gtk.Entry()
        self.entry.set_hexpand(True)
        self.entry.set_visibility(False)
        self.entry.set_placeholder_text("Secret password, eh…")
        self.entry.connect("activate", lambda *_: self.try_unlock())
        entry_row.append(self.entry)
        entry_row.append(button("Unlock 🔓", lambda *_: self.try_unlock()))
        entry_row.append(button("Disable dev", lambda *_: self.disable_dev()))
        dev.append(entry_row)

        hint = row_label("Hint: it's what you order at Tim Hortons "
                         "when you want two creams and two sugars.", "muted-label")
        hint.set_wrap(True)
        dev.append(hint)
        stack.append(dev)

        dev_toolbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dev_toolbox.append(row_label("Dev stuff already installed on this OS", "section-title"))
        dev_toolbox.append(row_label(
            "• /usr/bin/canadaos-shell  (the shell itself)\n"
            "• /etc/canadaos/sorryrc    (Sorry Terminal config)\n"
            "• /usr/local/bin/sorry, hockey, poursyrup, toque, timmy, beaver, beavertail, maple-lint",
            "muted-label"))
        stack.append(dev_toolbox)

        self.append(row_label("CanadaOS Settings", "app-title"))
        self.append(scroll)

    def set_wallpaper(self, value):
        config.set_key("wallpaper", value)
        self.win.desktop.set_wallpaper(value)
        self.state_label.set_text(
            "Dev Mode is ON. Sorry Terminal + Maple Syrup editor unlocked, eh!"
            if config.is_dev_mode() else
            "Dev Mode is OFF. Unlock for: 💻 Sorry Terminal, 🍁 Maple Syrup editor.")

    def try_unlock(self):
        guess = self.entry.get_text().strip().lower().replace(" ", "")
        accepted = {SECRET_PASSWORD, SECRET_PASSWORD.replace("-", "")}
        if guess in accepted:
            config.set_key("dev_mode", True)
            self.state_label.set_text("Dev Mode is ON. Sorry Terminal + Maple Syrup editor unlocked, eh!")
            base.info_dialog(self.win, "Welcome, eh!",
                             "Dev Mode unlocked! The Sorry Terminal and the Maple Syrup editor\n"
                             "are now yours to abuse politely.")
            self.entry.set_text("")
            self.win.desktop.refresh_dock()
            self.win.desktop.refresh_apps()
        else:
            base.info_dialog(self.win, "Not quite, eh.",
                             "Wrong password. Sorry.\n(Hint below, for polite people.)")

    def disable_dev(self):
        config.set_key("dev_mode", False)
        self.state_label.set_text(
            "Dev Mode is OFF. Unlock for: 💻 Sorry Terminal, 🍁 Maple Syrup editor.")
        self.win.desktop.refresh_dock()
        self.win.desktop.refresh_apps()
