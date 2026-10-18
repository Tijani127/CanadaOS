"""Notepad — plain text, polite, no dev perks. Different from Maple Syrup editor."""
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from . import base
from .base import app_root, button, row_label


class Notepad(Gtk.Box):
    def __init__(self, win, opts=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("app-root")
        self.win = win
        self.path = None

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_label = row_label("Notepad", "app-title")
        title_label.set_hexpand(True)
        toolbar.append(title_label)
        toolbar.append(button("New 📄", lambda *_: self.new_note()))
        toolbar.append(button("Open 📂", lambda *_: self.open_file()))
        toolbar.append(button("Save 💾", lambda *_: self.save(False)))
        toolbar.append(button("Save As…", lambda *_: self.save(True)))

        self.buffer = Gtk.TextBuffer()
        self.view = Gtk.TextView(buffer=self.buffer)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.view.set_vexpand(True)
        self.view.add_css_class("mono")

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self.view)

        self.status_label = base.status_bar("Notepad. Sorry, no autosave, eh.")
        self.char_count = row_label("chars 0 · words 0", "muted-label", align=Gtk.Align.END)
        self.char_count.set_hexpand(True)
        self.char_count.set_halign(Gtk.Align.END)
        self.file_label = row_label("", "muted-label")

        wrap_toggle = Gtk.CheckButton(label="Wrap")
        wrap_toggle.set_active(True)
        wrap_toggle.connect("toggled",
                            lambda b: self.view.set_wrap_mode(Gtk.WrapMode.WORD if b.get_active() else Gtk.WrapMode.NONE))

        self.status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.status.append(self.status_label)
        self.status.append(wrap_toggle)
        self.status.append(self.file_label)
        self.status.append(self.char_count)
        self.append(toolbar)
        self.append(scroller)
        self.append(self.status)

        self.buffer.connect("changed", self._changed)
        self._count()

        if opts and opts.get("path"):
            self.load_path(opts["path"])

    def _changed(self, buf):
        self._count()

    def _count(self):
        text = self._text()
        n_chars = len(text)
        n_words = len(text.split()) or 0
        self.char_count.set_text("chars {} · words {}".format(n_chars, n_words))

    def _text(self):
        start, end = self.buffer.get_bounds()
        return self.buffer.get_text(start, end, False)

    def new_note(self):
        self.buffer.set_text("")
        self.path = None
        self.file_label.set_text("(unsaved)")

    def load_path(self, path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                self.buffer.set_text(fh.read())
            self.path = path
            self.file_label.set_text(path)
            self.status_label.set_text("Loaded " + path)
        except OSError as ex:
            base.info_dialog(self.win, "Sorry", "Couldn't read that file, eh:\n{}".format(ex))

    def open_file(self):
        base.choose_open_file(self.win, lambda p: self.load_path(p) if p else None,
                              mime=["text/plain"])

    def save(self, ask_path):
        base.choose_save_file(self.win, lambda p: self.write(p) if p else None,
                              suggested="note.txt")

    def write(self, path):
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._text())
            self.path = path
            self.file_label.set_text(path)
            self.status_label.set_text("Saved to " + path)
        except OSError as ex:
            base.info_dialog(self.win, "Sorry", "Save failed, sorry:\n{}".format(ex))


def build(win, opts=None):
    return Notepad(win, opts=opts)
