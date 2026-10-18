"""Sorry Terminal — real bash (VTE if available, PTY-lite otherwise), Canadian style."""
import os

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

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


def _shell_argv():
    wrapper = "/usr/local/bin/sorry-shell"
    if os.access(wrapper, os.X_OK):
        return [wrapper]
    return ["/bin/bash", "-l"]


class Terminal(Gtk.Box):
    def __init__(self, win, opts=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("app-root")
        self.win = win

        self._vte = _load_vte()
        if self._vte is None:
            self._lite_terminal()
            return

        term = self._vte.Terminal()
        self._apply_colors(term)

        err = self._spawn_shell(term, _shell_argv())
        if err is not None:
            self._lite_terminal(note="VTE spawn failed ({}), eh — using the lite terminal.".format(err))
            return

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(term)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.append(button("New shell", lambda *_: self.win.desktop.launch("terminal")))
        bar.append(row_label("Real bash. Easter eggs: sorry · hockey · poursyrup · toque · timmy", "muted-label"))

        self.append(bar)
        self.append(scroller)

    def _spawn_shell(self, term, argv):
        """Spawn the shell with a FULL env (PATH/HOME preserved), tolerating
        different PyGObject spawn_async arities. Returns None on success."""
        from gi.repository import GLib
        wd = os.path.expanduser("~")
        env = ["{}={}".format(k, v) for k, v in os.environ.items()]
        env.append("CANADAOS=1")
        env.append("TERM=xterm-256color")
        flags = GLib.SpawnFlags.DEFAULT
        last_err = None
        attempts = [
            (self._vte.PtyFlags.DEFAULT, wd, argv, env, flags, None),
            (self._vte.PtyFlags.DEFAULT, wd, argv, env, flags, None, None),
            (self._vte.PtyFlags.DEFAULT, wd, argv, env, flags, None, None, None),
        ]
        for args in attempts:
            try:
                term.spawn_async(*args)
                return None
            except TypeError as ex:
                last_err = ex
        return last_err

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

    def _lite_terminal(self, note=None):
        """No VTE? No problem: a real bash over a PTY, line-entry style."""
        import re
        import subprocess

        out = Gtk.TextView()
        buf = out.get_buffer()
        out.set_editable(False)
        out.set_cursor_visible(False)
        out.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        out.set_vexpand(True)
        out.add_css_class("mono")
        out.get_buffer().insert(out.get_buffer().get_end_iter(),
                                "Sorry Terminal (lite) — real bash beneath, eh.\n"
                                "Type a command below and press Enter.\n\n")
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(out)

        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry = Gtk.Entry()
        entry.set_hexpand(True)
        entry.set_placeholder_text("Type a command, eh… (try: sorry, hockey, poursyrup)")
        entry_row.append(entry)

        # same shell wrapper as the VTE path
        shell = _shell_argv()
        import pty as _pty
        master, slave = _pty.openpty()
        env = dict(os.environ)
        env.setdefault("TERM", "xterm-256color")
        env["CANADAOS"] = "1"
        try:
            subprocess.Popen(shell, stdin=slave, stdout=slave, stderr=slave,
                             cwd=os.path.expanduser("~"), env=env,
                             start_new_session=True)
        finally:
            try:
                os.close(slave)
            except OSError:
                pass
        fd = master

        filler = Gtk.Box()
        filler.set_hexpand(True)
        entry_row.append(filler)
        entry_row.append(button("Run ⏎", lambda *_: self._send(entry, buf, out, fd)))
        entry.connect("activate", lambda e: self._send(entry, buf, out, fd))

        status = base.status_bar(
            (note or "") + " Lite mode: line-by-line input; full xterm features need gir1.2-vte-3.91.")

        self.append(entry_row)
        self.append(scroller)
        self.append(status)

        ansi = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\r")

        def _pump(_src, _cond):
            try:
                data = os.read(fd, 4096)
            except OSError:
                return False
            if not data:
                return False
            cleaned = ansi.sub("", data.decode("utf-8", "replace"))
            buf.insert(buf.get_end_iter(), cleaned)
            out.scroll_mark_onscreen(buf.get_insert())
            return True

        GLib.io_add_watch(fd, GLib.IOCondition.IN, _pump)

    @staticmethod
    def _send(entry, buf, out, fd):
        line = entry.get_text()
        entry.set_text("")
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        except OSError as ex:
            buf.insert(buf.get_end_iter(), "\n(write failed: {})\n".format(ex))
            out.scroll_mark_onscreen(buf.get_insert())

    def build(self):
        return self


def build(win, opts=None):
    return Terminal(win, opts=opts)
