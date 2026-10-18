"""Shared helpers for CanadaOS apps — dialogs, status bars, async threads, eh."""
import threading
import json

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib

from .. import config

CANADIAN_COLORS = [
    ("Maple Red", "#d52b1e"),
    ("Beaver Brown", "#7b4b2a"),
    ("Snow", "#f4f7fa"),
    ("Rockies Blue", "#1e6e8c"),
    ("Forest Green", "#2f6b44"),
    ("Prairie Gold", "#e9b44c"),
    ("Tundra Grey", "#7f8c99"),
    ("Loonie Loon", "#4f6d7a"),
    ("Double-Double Tan", "#c9a66b"),
]


def is_dev_mode() -> bool:
    return config.is_dev_mode()


def app_root(orientation=Gtk.Orientation.VERTICAL, spacing=8):
    box = Gtk.Box(orientation=orientation, spacing=spacing)
    box.add_css_class("app-root")
    box.set_vexpand(True)
    box.set_hexpand(True)
    return box


def status_bar(text=""):
    label = Gtk.Label(label=text)
    label.add_css_class("statusbar")
    label.set_halign(Gtk.Align.START)
    label.set_hexpand(True)
    label.set_ellipsize(3)  # PEND
    return label


def row_label(text, css=None, align=Gtk.Align.START):
    label = Gtk.Label(label=text)
    if css:
        label.add_css_class(css)
    label.set_halign(align)
    return label


def button(text, callback=None, css=None):
    btn = Gtk.Button(label=text)
    if css:
        btn.add_css_class(css)
    if callback:
        btn.connect("clicked", callback)
    return btn


def lock_content(win, app_info):
    """Locked Dev Mode app screen."""
    box = app_root(spacing=14)
    box.set_valign(Gtk.Align.CENTER)
    box.set_halign(Gtk.Align.CENTER)

    title = row_label("🔒 {} is locked, eh".format(app_info.title), "app-title")
    desc = row_label("Did you know: in most countries this app ships with the OS.\n"
                     "In CanadaOS it arrives only for Developers who pack up their toque and gear up.",
                     "muted-label")
    desc.set_justify(Gtk.Justification.CENTER)
    desc.set_wrap(True)

    btn = button("Open Settings ⚙", lambda *_: win.desktop.launch("settings"), "app-tile")

    box.append(title)
    box.append(desc)
    box.append(btn)
    return box


def info_dialog(parent, title, text):
    dlg = Gtk.MessageDialog(transient_for=parent, modal=True,
                            message_type=Gtk.MessageType.INFO,
                            buttons=Gtk.ButtonsType.OK, text=text)
    dlg.set_title(title)
    dlg.connect("response", lambda d, *a: d.destroy())
    dlg.show()


def confirm_dialog(parent, title, text, on_yes):
    dlg = Gtk.MessageDialog(transient_for=parent, modal=True,
                            message_type=Gtk.MessageType.QUESTION,
                            text=text)
    dlg.set_title(title)
    dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
    dlg.add_button("Sorry — yes", Gtk.ResponseType.OK)
    dlg.connect("response", lambda d, resp: (on_yes() if resp == Gtk.ResponseType.OK else None,
                                             d.destroy()))
    dlg.show()


def choose_open_file(parent, on_done, mime=None):
    dlg = Gtk.FileChooserNative.new("Open file", parent, Gtk.FileChooserAction.OPEN,
                                    "Open", "Cancel")
    if mime:
        filt = Gtk.FileFilter()
        filt.set_name("Supported")
        for m in (mime if isinstance(mime, (list, tuple)) else [mime]):
            filt.add_mime_type(m)
        dlg.add_filter(filt)
    dlg.show(lambda d, resp: _yield_file(d, resp, "open", on_done))


def choose_save_file(parent, on_done, suggested=None):
    dlg = Gtk.FileChooserNative.new("Save file", parent, Gtk.FileChooserAction.SAVE,
                                    "Save", "Cancel")
    if suggested:
        dlg.set_current_name(suggested)
    dlg.set_do_overwrite_confirmation(True)
    dlg.show(lambda d, resp: _yield_file(d, resp, "save", on_done))


def _yield_file(dlg, resp, _kind, on_done):
    f = dlg.get_file() if resp == Gtk.ResponseType.ACCEPT else None
    on_done(f.get_path() if f else None)


def run_async(fn, on_done):
    """Run fn in a thread; on_done receives (result-or-exception) in main loop."""
    def runner():
        try:
            result = fn()
        except Exception as ex:  # noqa: BLE001 — politeness first
            result = ex
        GLib.idle_add(lambda: on_done(result))
    threading.Thread(target=runner, daemon=True).start()
