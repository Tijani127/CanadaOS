"""File explorer — folders and files, with manners."""
import os
import shutil
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from . import base
from .base import app_root, button, row_label

TEXT_LIKE = {".txt", ".md", ".log", ".rst", ".ini", ".conf", ".yaml", ".yml", ".toml", ".json"}
TEXT_LIKE_ON = {".maple"}


def build(win, opts=None):
    return Files(win, opts=opts)


class Files(Gtk.Box):
    def __init__(self, win, opts=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("app-root")
        self.win = win
        self.selected = None

        self.cwd = Path.home()

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.append(button("⬆ Up", lambda *_: self.go_up()))
        toolbar.append(button("🏠 Home", lambda *_: self.go_home()))
        toolbar.append(button("⟳ Refresh", lambda *_: self.refresh()))
        self.crumbs = row_label("", "muted-label")
        self.crumbs.set_hexpand(True)
        self.crumbs.set_ellipsize(3)
        toolbar.append(self.crumbs)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.new_name = Gtk.Entry()
        self.new_name.set_placeholder_text("New folder/file name…")
        self.new_name.set_hexpand(True)
        actions.append(self.new_name)
        actions.append(button("New Folder", lambda *_: self.new_folder()))
        actions.append(button("New File", lambda *_: self.new_file()))
        actions.append(button("Rename", lambda *_: self.rename()))
        actions.append(button("Delete 🗑", lambda *_: self.delete()))

        self.listbox = Gtk.ListBox()
        self.listbox.set_vexpand(True)
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self.listbox)

        self.status = base.status_bar("Click a folder to pop in; double-click files to open.")

        self.append(toolbar)
        self.append(actions)
        self.append(scroller)
        self.append(self.status)

        self.listbox.connect("row_selected", self.on_row_selected)
        self.listbox.connect("row_activated", self.on_row_activated)
        self.refresh()
        if opts and opts.get("path"):
            p = Path(opts["path"])
            self.open_item(p)

    def refresh(self):
        while True:
            child = self.listbox.get_first_child()
            if child is None: break
            self.listbox.remove(child)
        try:
            entries = sorted(
                self.cwd.iterdir(),
                key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            entries = []
            self.status.set_text("Sorry — permission denied.")
        self.selected = None
        for path in entries:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            box.set_margin_start(8)
            glyph = "📁" if path.is_dir() else self._icon(path)
            name = Gtk.Label(label=(glyph + "  " + path.name))
            name.set_hexpand(True)
            name.set_halign(Gtk.Align.START)
            kind = row_label("dir" if path.is_dir() else "file", "muted-label")
            box.append(name)
            box.append(kind)
            row.set_child(box)
            row._path = path  # stash
            self.listbox.append(row)
        self.crumbs.set_text(str(self.cwd))

    @staticmethod
    def _icon(path):
        ext = path.suffix.lower()
        if ext in TEXT_LIKE_ON:
            return "🍁"
        if ext in TEXT_LIKE:
            return "📄"
        if ext in (".png", ".jpg", ".jpeg", ".svg", ".gif"):
            return "🖼️"
        return "📎"

    def go_up(self):
        self.cwd = self.cwd.parent
        self.refresh()

    def go_home(self):
        self.cwd = Path.home()
        self.refresh()

    def on_row_selected(self, listbox, row):
        if row is None or not hasattr(row, "_path"):
            return
        self.selected = row._path
        if row._path.is_dir():
            self.cwd = row._path
            self.refresh()

    def on_row_activated(self, listbox, row):
        if row is None or not hasattr(row, "_path"):
            return
        self.open_item(row._path)

    def open_item(self, path):
        if path.is_dir():
            self.cwd = path
            self.refresh()
            return
        ext = path.suffix.lower()
        if ext in TEXT_LIKE_ON:
            self.win.desktop.launch("syrup", {"path": str(path)})
        elif ext in TEXT_LIKE:
            self.win.desktop.launch("notepad", {"path": str(path)})
        else:
            base.info_dialog(self.win, "Sorry",
                             "Not sure how to open {} politely.\n"
                             "(.maple → Maple Syrup editor, text → Notepad)".format(path.suffix or "file"))

    def new_folder(self):
        name = (self.new_name.get_text() or "").strip()
        if not name:
            base.info_dialog(self.win, "Hmm.", "Type a name first.")
            return
        try:
            (self.cwd / name).mkdir(parents=False, exist_ok=True)
            self.refresh()
        except OSError as ex:
            base.info_dialog(self.win, "Sorry", "No can do:\n{}".format(ex))

    def new_file(self):
        name = (self.new_name.get_text() or "").strip()
        if not name:
            base.info_dialog(self.win, "Hmm.", "Type a name first.")
            return
        try:
            target = self.cwd / name
            target.touch()
            self.refresh()
        except OSError as ex:
            base.info_dialog(self.win, "Sorry", "Failed:\n{}".format(ex))

    def rename(self):
        name = (self.new_name.get_text() or "").strip()
        if not name or not self.selected:
            return
        try:
            self.selected.rename(self.cwd / name)
            self.refresh()
        except OSError as ex:
            base.info_dialog(self.win, "Sorry", "Rename failed:\n{}".format(ex))

    def delete(self):
        if not self.selected:
            return

        def confirmed():
            try:
                target = self.selected
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            except OSError as ex:
                base.info_dialog(self.win, "Sorry", "Delete failed:\n{}".format(ex))
            self.refresh()

        base.confirm_dialog(self.win, "Delete?",
                            "Delete {}? I've apologized in advance.".format(self.selected.name),
                            confirmed)
