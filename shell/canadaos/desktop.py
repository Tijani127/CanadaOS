"""CanadaOS desktop shell: top bar, dock, internal windows drawn on a canvas."""
import os
import time

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk

from . import config
from .apps import APPS, get_app, factory_for


class CanadaWindow(Gtk.Box):
    """A floating app window drawn as a widget on the desktop canvas.

    Design notes (learned the hard way, eh):
    - The content MUST vexpand, or apps collapse to their minimum size and
      look "empty" inside a big window frame.
    - Never re-parent the window widget during click/drag gestures: removing
      a widget from the canvas resets every gesture sequence on it, which is
      how we used to break the close button and make dragging glitch out.
      Re-parenting (bring-to-front) is only allowed as an explicit action
      (dock click, un-minimize), never inside a gesture handler.
    """

    def __init__(self, desktop, app_info):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.desktop = desktop
        self.app_info = app_info
        self.pos = (60, 60)
        self.add_css_class("canada-window")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.add_css_class("canada-header")
        title = Gtk.Label(label="{}  {}".format(app_info.emoji, app_info.title))
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        header.append(title)
        for label, cb, css in [("—", self._minimize, "win-btn"),
                               ("□", self._maximize, "win-btn"),
                               ("✕", self._close, "win-btn close-btn")]:
            btn = Gtk.Button(label=label)
            btn.add_css_class(css)
            btn.connect("clicked", cb)
            header.append(btn)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_box.add_css_class("canada-content")
        try:
            factory = factory_for(app_info)
            content = factory(self, {})
        except Exception:
            # One broken app must never take down the whole desktop, eh.
            import traceback
            traceback.print_exc()
            err = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            err.add_css_class("app-root")
            msg = Gtk.Label(label="{} — apologetically crashed, sorry, eh 🍁\n\n(run the debug session for the traceback)".format(app_info.title))
            msg.set_wrap(True)
            msg.set_sensitive(False)
            err.append(msg)
            content = err
        content_box.append(content)

        content_overlay = Gtk.Overlay()
        content_overlay.set_child(content_box)
        content_overlay.set_vexpand(True)   # THE fix for "apps look empty"
        content_overlay.set_hexpand(True)

        grip = Gtk.Box()
        grip.set_size_request(18, 18)
        grip.add_css_class("resize-grip")
        grip.set_halign(Gtk.Align.END)
        grip.set_valign(Gtk.Align.END)
        grip.set_margin_end(2)
        grip.set_margin_bottom(2)
        grip.set_opacity(0.6)
        content_overlay.add_overlay(grip)
        grip_drag = Gtk.GestureDrag()
        grip_drag.connect("drag-begin", self._resize_begin)
        grip_drag.connect("drag-update", self._resize_update)
        grip_drag.connect("drag-end", self._resize_end)
        grip.add_controller(grip_drag)

        self.set_size_request(app_info.width, app_info.height)
        self.append(header)
        self.append(content_overlay)

        # Moving (header drag). No re-parenting inside the gesture.
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        drag.connect("drag-end", self._drag_end)
        header.add_controller(drag)

        self._content = content
        self._move_start = None
        self._resize_start = None
        self._was_max = False
        self._prev_pos = None
        self._prev_size = None

    # ---------- window chrome ----------
    def _minimize(self, btn):
        self.desktop.minimize_window(self)

    def _close(self, btn):
        self.desktop.close_window(self)

    def _maximize(self, btn):
        if self._was_max:
            self.pos = self._prev_pos or (60, 60)
            self.desktop.reposition(self)
            self.set_size_request(self._prev_size)
            self.app_info.width, self.app_info.height = self._prev_size
            self._was_max = False
        else:
            self._prev_size = (self.app_info.width, self.app_info.height)
            self._prev_pos = self.pos
            self.pos = (0, 0)
            self.desktop.reposition(self)
            w, h = self.desktop.get_canvas_size()
            self.set_size_request(w, h)
            self.app_info.width, self.app_info.height = w, h
            self._was_max = True
        self.set_size_request(max(self.app_info.width, 360), max(self.app_info.height, 240))

    # ---------- moving ----------
    def _drag_begin(self, gesture, start_x, start_y):
        if self._was_max:
            return
        self._move_start = self.pos

    def _drag_update(self, gesture, offset_x, offset_y):
        if self._was_max or not self._move_start:
            return
        last = getattr(self, "_last_delta", (0, 0))
        dx, dy = offset_x - last[0], offset_y - last[1]
        self._last_delta = (offset_x, offset_y)
        x = max(0, self.pos[0] + int(dx))
        y = max(0, self.pos[1] + int(dy))
        self.pos = (x, y)
        self.desktop.reposition(self)

    def _drag_end(self, gesture, offset_x, offset_y):
        self._move_start = None
        self._last_delta = (0, 0)

    # ---------- resizing ----------
    def _resize_begin(self, gesture, start_x, start_y):
        self._resize_start = (self.app_info.width, self.app_info.height)

    def _resize_update(self, gesture, offset_x, offset_y):
        if not self._resize_start or self._was_max:
            return
        new_w = max(360, self._resize_start[0] + int(offset_x))
        new_h = max(240, self._resize_start[1] + int(offset_y))
        self.set_size_request(new_w, new_h)
        self.app_info.width, self.app_info.height = new_w, new_h

    def _resize_end(self, gesture, offset_x, offset_y):
        self._resize_start = None


class TopBar(Gtk.Box):
    def __init__(self, desktop):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.add_css_class("canada-topbar")
        self.desktop = desktop

        logo = Gtk.Label(label="🍁 CanadaOS")
        logo.add_css_class("topbar-logo")
        self.append(logo)

        menu_btn = Gtk.MenuButton(label="Eh-Menu ▾")
        menu_btn.add_css_class("topbar-menu-btn")
        menu_btn.set_popover(self._build_launcher(desktop))
        self.append(menu_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.append(spacer)

        self.dev_badge = Gtk.Label(label="DEV 🍁 ON" if config.is_dev_mode() else "")
        self.dev_badge.add_css_class("dev-badge")
        self.append(self.dev_badge)

        self.clock = Gtk.Label(label="")
        self.clock.add_css_class("clock")
        self.append(self.clock)
        self._tick_clock()
        GLib.timeout_add_seconds(10, self._tick_clock)

    def _tick_clock(self):
        self.clock.set_text(time.strftime("%a %H:%M") + " 🍁")
        return True

    def _build_launcher(self, desktop):
        popover = Gtk.Popover()
        grid = Gtk.FlowBox()
        grid.set_max_children_per_line(3)
        grid.set_min_children_per_line(3)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.add_css_class("launcher-grid")
        for info in APPS:
            label = info.emoji + "  " + info.title
            if info.dev_only and not config.is_dev_mode():
                label += " 🔒"
            tile = Gtk.Button(label=label)
            tile.add_css_class("app-tile")
            tile.set_tooltip_text(info.desc)
            def on_tile(btn, aid=info.app_id):
                desktop.launch(aid)
                popover.popdown()
            tile.connect("clicked", on_tile)
            grid.append(tile)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        note = Gtk.Label(label="Apps, eh? Locked tiles need Dev Mode (Settings → Dev Mode).")
        note.add_css_class("muted-label")
        note.set_wrap(True)
        box.append(note)
        box.append(grid)
        box.set_margin_top(10)
        box.set_margin_start(10)
        box.set_margin_bottom(10)
        box.set_margin_end(10)
        popover.set_child(box)
        popover.set_size_request(400, 260)
        return popover


class Dock(Gtk.Box):
    def __init__(self, desktop):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.add_css_class("canada-dock")
        self.desktop = desktop
        self.tasks_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.refresh()

    def refresh(self):
        while True:
            child = self.get_first_child()
            if child is None or child is self.tasks_box:
                break
            self.remove(child)
        for info in APPS:
            label = info.emoji + ("🔒" if info.dev_only and not config.is_dev_mode() else "")
            btn = Gtk.Button(label=label)
            btn.add_css_class("dock-btn")
            btn.set_tooltip_text("{} — {}{}".format(
                info.title, info.desc, " (needs Dev Mode)" if info.dev_only else ""))
            def on_btn(btn, aid=info.app_id):
                self.desktop.launch(aid)
            btn.connect("clicked", on_btn)
            self.append(btn)
        filler = Gtk.Box()
        filler.set_hexpand(True)
        self.append(filler)
        self.append(self.tasks_box)
        self.sync_tasks()

    def sync_tasks(self):
        while True:
            child = self.tasks_box.get_first_child()
            if child is None:
                break
            self.tasks_box.remove(child)
        for win in list(self.desktop.minimized):
            pill = Gtk.Button(label=win.app_info.emoji + " " + win.app_info.title)
            pill.add_css_class("task-pill")
            pill.connect("clicked", lambda b, w=win: self.desktop.unminimize_window(w))
            self.tasks_box.append(pill)


class DesktopWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("CanadaOS")
        self.windows = {}
        self.minimized = []
        self._cascade = 0

        self.set_default_size(1280, 800)
        try:
            self.fullscreen()
        except Exception:
            pass

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("canada-root")

        self.canvas = Gtk.Fixed()
        self.canvas.add_css_class("canada-desktop")
        self.canvas.add_css_class("wall-" + config.wallpaper())
        self.canvas.set_hexpand(True)
        self.canvas.set_vexpand(True)

        leaf = Gtk.Label(label="🍁")
        leaf.add_css_class("canada-leaf")
        leaf.set_sensitive(False)
        self.canvas.put(leaf, 60, 120)

        brand = Gtk.Label(label="CanadaOS — est. 1867, eh.")
        brand.add_css_class("brand")
        brand.set_sensitive(False)
        self.canvas.put(brand, 24, 24)

        welcome = Gtk.Label(label=(
            "Welcome to CanadaOS 🍁\n\n"
            "The Eh-Menu (top-left) opens apps. Nothing opens by itself, we promise, eh.\n"
            "Settings ⚙ has the Dev Mode unlock. Hockey Arena 🏒 is live.\n"
            "All windows can be dragged by their title bars."))
        welcome.add_css_class("welcome-note")
        welcome.set_sensitive(False)
        welcome.set_justify(Gtk.Justification.CENTER)
        welcome.set_visible(True)
        try:
            # GTK 4.8+: let clicks fall through to the desktop beneath.
            welcome.set_can_target(False)
        except Exception:
            pass
        self.welcome = welcome

        # GTK4 removed the "resize"/"size-allocate" signals on widgets, so we
        # center the welcome note with an Overlay instead of signal math;
        # GTK centers overlay children for us via halign/valign.
        self.canvas_overlay = Gtk.Overlay()
        self.canvas_overlay.set_child(self.canvas)
        self.canvas_overlay.add_overlay(self.welcome)
        self.canvas_overlay.set_hexpand(True)
        self.canvas_overlay.set_vexpand(True)

        self.topbar = TopBar(self)
        self.dock = Dock(self)

        root.append(self.topbar)
        root.append(self.canvas_overlay)
        root.append(self.dock)
        self.set_child(root)

        # Headless screenshot mode for CI: open a couple of apps so the
        # smoke-test screenshot actually shows app content.
        if os.environ.get("CANADAOS_SMOKE"):
            self.launch("settings")
            self.launch("notepad")

    # ---------- canvas helpers ----------
    def get_canvas_size(self):
        w, h = self.canvas.get_allocated_width(), self.canvas.get_allocated_height()
        if w <= 1:
            w, h = self.get_allocated_width(), max(400, self.get_allocated_height() - 90)
        return w, h

    def set_wallpaper(self, value):
        for name in ("wall-midnight-yukon", "wall-forest-night", "wall-prairie-night"):
            if self.canvas.has_css_class(name):
                self.canvas.remove_css_class(name)
        self.canvas.add_css_class("wall-{}".format(value))

    def reposition(self, win):
        try:
            self.canvas.move(win, win.pos[0], win.pos[1])
        except Exception:
            pass

    def _cascade_pos(self):
        self._cascade += 1
        off = (self._cascade * 70) % 350
        return 80 + off, 60 + off

    def launch(self, app_id, opts=None):
        info = get_app(app_id)
        if info is None:
            return
        if app_id in self.windows:
            win = self.windows[app_id]
            self.unminimize_window(win)
            self._deliver_opts(win, opts)
            self.raise_window(win)
            return win
        win = CanadaWindow(self, info)
        self.windows[app_id] = win
        pos = self._cascade_pos()
        win.pos = pos
        self.canvas.put(win, pos[0], pos[1])
        self.refresh_welcome()
        self.raise_window(win)
        self._deliver_opts(win, opts)
        return win

    def raise_window(self, win):
        """Explicit bring-to-front (dock click / unminimize). Never call from a gesture."""
        pos = win.pos
        try:
            self.canvas.remove(win)
            self.canvas.put(win, pos[0], pos[1])
        except Exception:
            pass
        try:
            win._content.grab_focus()
        except Exception:
            pass

    def _deliver_opts(self, win, opts):
        if not opts:
            return
        loader = getattr(win._content, "load_path", None)
        path = opts.get("path")
        if loader and path:
            try:
                loader(path)
            except Exception:
                pass

    def minimize_window(self, win):
        win.set_visible(False)
        if win not in self.minimized:
            self.minimized.append(win)
        self.dock.sync_tasks()

    def unminimize_window(self, win):
        win.set_visible(True)
        if win in self.minimized:
            self.minimized.remove(win)
        self.dock.sync_tasks()
        self.raise_window(win)

    def close_window(self, win):
        app_id = getattr(win.app_info, "app_id", None)
        self.windows.pop(app_id, None)
        if win in self.minimized:
            self.minimized.remove(win)
        try:
            self.canvas.remove(win)
        except Exception:
            pass
        self.dock.sync_tasks()
        self.refresh_welcome()

    def refresh_welcome(self):
        # Hide the welcome note once there is at least one window on screen.
        self.welcome.set_visible(len(self.windows) == 0)

    def refresh_dock(self):
        self.dock.refresh()
        # Rebuild Dev-Mode windows so locked/unlocked content matches state.
        for app_id in list(self.windows.keys()):
            win = self.windows[app_id]
            if win.app_info.dev_only:
                self.close_window(win)
                self.launch(app_id)
        self.refresh_badge()

    def refresh_badge(self):
        self.topbar.dev_badge.set_text("DEV 🍁 ON" if config.is_dev_mode() else "")

    def refresh_apps(self):
        self.refresh_badge()
