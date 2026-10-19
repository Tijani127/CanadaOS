"""Shared helpers for CanadaOS apps — dialogs, status bars, async threads, eh."""
import threading
from pathlib import Path

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

    title = row_label("🔒 {} is locked".format(app_info.title), "app-title")
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


def _overlay_for(win):
    """Our app windows expose their Gtk.Overlay; system dialogs can't be used
    here because our 'windows' are widgets, not top-level GtkWindows, and there
    is no window manager to stack a dialog above the fullscreen shell, eh."""
    return getattr(win, "content_overlay", None)


def _dismiss(scrim):
    try:
        scrim.get_parent().remove_overlay(scrim)
    except Exception:
        pass


def _panel(title, width=460):
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    card.add_css_class("modal-card")
    card.set_halign(Gtk.Align.CENTER)
    card.set_valign(Gtk.Align.CENTER)
    card.set_size_request(width, -1)
    card.append(row_label(title, "app-title"))
    return card


def info_dialog(parent, title, text):
    ov = _overlay_for(parent)
    if ov is None:
        print("[canadaos][{}] {}".format(title, text))
        return
    scrim = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    scrim.add_css_class("modal-scrim")
    card = _panel(title)
    body = row_label(text, "muted-label")
    body.set_wrap(True)
    card.append(body)
    card.append(button("OK", lambda *_: _dismiss(scrim), "app-tile"))
    scrim.append(card)
    ov.add_overlay(scrim)


def confirm_dialog(parent, title, text, on_yes):
    ov = _overlay_for(parent)
    if ov is None:
        print("[canadaos][{}] {}".format(title, text))
        return
    scrim = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    scrim.add_css_class("modal-scrim")
    card = _panel(title)
    body = row_label(text, "muted-label")
    body.set_wrap(True)
    card.append(body)
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.set_halign(Gtk.Align.CENTER)
    row.append(button("Cancel", lambda *_: _dismiss(scrim), "app-tile"))
    row.append(button("Yes",
                      lambda *_: (_dismiss(scrim), on_yes()), "app-tile"))
    card.append(row)
    scrim.append(card)
    ov.add_overlay(scrim)


def _file_browser_card():
    """Shared in-app directory browser for the file dialogs.
    Returns {crumbs, scroller, refresh, selected, current, on_file}."""
    current = {"dir": Path.home()}
    selected = {"path": None}

    crumbs = row_label("", "muted-label")
    crumbs.set_ellipsize(3)
    lb = Gtk.ListBox()
    scroller = Gtk.ScrolledWindow()
    scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scroller.set_vexpand(True)
    scroller.set_child(lb)

    def refresh():
        while True:
            child = lb.get_first_child()
            if child is None:
                break
            lb.remove(child)
        crumbs.set_text(str(current["dir"]))
        selected["path"] = None
        try:
            entries = sorted(current["dir"].iterdir(),
                             key=lambda p: (p.is_file(), p.name.lower()))
        except (PermissionError, OSError):
            entries = []
        for path in entries:
            glyph = "📁" if path.is_dir() else "📄"
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            box.set_margin_start(8)
            box.append(Gtk.Label(label="{}  {}".format(glyph, path.name)))
            row.set_child(box)
            row._path = path
            lb.append(row)

    def on_row_selected(_lb, row):
        selected["path"] = getattr(row, "_path", None) if row is not None else None

    def on_row_activated(_lb, row):
        p = getattr(row, "_path", None) if row is not None else None
        if p is None:
            return
        if p.is_dir():
            current["dir"] = p
            refresh()
        elif "on_file" in state and state["on_file"]:
            state["on_file"](p)

    def up(_btn=None):
        current["dir"] = current["dir"].parent
        refresh()

    state = {"crumbs": crumbs, "scroller": scroller, "lb": lb,
             "refresh": refresh, "up": up, "current": current,
             "selected": selected, "on_file": None}
    lb.connect("row_selected", on_row_selected)
    lb.connect("row_activated", on_row_activated)
    return state


def choose_open_file(parent, on_done, mime=None):
    """In-app file picker (system file chooser can't be parented from a
    non-window widget). on_done receives a path string, or None if cancelled."""
    ov = _overlay_for(parent)
    if ov is None:
        print("[canadaos] open dialog unavailable")
        return

    def done(path):
        _dismiss(scrim)
        on_done(str(path) if path else None)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    card.add_css_class("modal-card")
    card.set_halign(Gtk.Align.CENTER)
    card.set_valign(Gtk.Align.CENTER)
    card.set_size_request(520, 480)
    card.append(row_label("Open a file", "app-title"))

    fb = _file_browser_card()
    fb["on_file"] = done
    card.append(fb["crumbs"])
    card.append(fb["scroller"])
    fb["refresh"]()

    actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    actions.append(button("⬆ Up", fb["up"], "app-tile"))
    actions.append(button(
        "Open 📂",
        lambda *_: done(fb["selected"]["path"]
                        if fb["selected"]["path"] is not None and
                        fb["selected"]["path"].is_file() else None),
        "app-tile"))
    spacer = Gtk.Box()
    spacer.set_hexpand(True)
    actions.append(spacer)
    actions.append(button("Cancel", lambda *_: done(None)))
    card.append(actions)

    scrim = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    scrim.add_css_class("modal-scrim")
    scrim.append(card)
    ov.add_overlay(scrim)


def choose_save_file(parent, on_done, suggested=None):
    """In-app save picker. on_done receives a path string, or None."""
    ov = _overlay_for(parent)
    if ov is None:
        print("[canadaos] save dialog unavailable")
        return

    def done(path):
        _dismiss(scrim)
        on_done(str(path) if path else None)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    card.add_css_class("modal-card")
    card.set_halign(Gtk.Align.CENTER)
    card.set_valign(Gtk.Align.CENTER)
    card.set_size_request(520, 480)
    card.append(row_label("Save as…", "app-title"))

    name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    name_entry = Gtk.Entry()
    name_entry.set_hexpand(True)
    name_entry.set_text(suggested or "")
    name_entry.set_placeholder_text("File name…")
    name_row.append(name_entry)
    card.append(name_row)

    fb = _file_browser_card()
    fb["on_file"] = lambda p: name_entry.set_text(p.name)  # pick a name hint
    card.append(fb["crumbs"])
    card.append(fb["scroller"])
    fb["refresh"]()

    actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    actions.append(button("⬆ Up", fb["up"], "app-tile"))
    actions.append(button(
        "Save 💾",
        lambda *_: done(str(fb["current"]["dir"] /
                        (name_entry.get_text().strip() or "untitled"))),
        "app-tile"))
    spacer = Gtk.Box()
    spacer.set_hexpand(True)
    actions.append(spacer)
    actions.append(button("Cancel", lambda *_: done(None)))
    card.append(actions)

    scrim = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    scrim.add_css_class("modal-scrim")
    scrim.append(card)
    ov.add_overlay(scrim)


def run_async(fn, on_done):
    """Run fn in a thread; on_done receives (result-or-exception) in main loop."""
    def runner():
        try:
            result = fn()
        except Exception as ex:  # noqa: BLE001 — politeness first
            result = ex
        GLib.idle_add(lambda: on_done(result))
    threading.Thread(target=runner, daemon=True).start()
