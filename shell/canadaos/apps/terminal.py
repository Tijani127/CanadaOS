"""Sorry Terminal — a normal terminal (real VTE/bash) with Canadian commands."""
import os

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from . import base
from .base import app_root, button, row_label

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
            self._lite_terminal(note="VTE spawn failed ({}) — using the lite terminal.".format(err))
            return

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(term)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.append(button("New shell", lambda *_: self.win.desktop.launch("terminal")))
        bar.append(row_label(
            "bash • commands: sorry · hockey · poursyrup · toque · beaver · timmy · maple-lint",
            "muted-label"))

        self.append(scroller)
        self.append(bar)

    def _spawn_shell(self, term, argv):
        """Spawn the shell with a FULL env (PATH/HOME preserved).

        VTE 0.80 (gir 3.91) changed spawn_async's shape to
        (pty_flags, wd, argv, envv, spawn_flags, child_setup, timeout,
        cancellable, callback): a plain-integer `timeout` sits AFTER
        child_setup. The old arity-guessing attempts fed None into that
        slot — "Argument 9 does not allow None as a value" — which
        silently downgraded this terminal to the lite one on every boot
        so far. Attempt shapes verified against the published PyGObject
        Vte-3.81 API docs; every candidate supplies timeout=-1 now.
        Returns None on success."""
        from gi.repository import GLib
        wd = os.path.expanduser("~")
        env = ["{}={}".format(k, v) for k, v in os.environ.items()]
        env.append("CANADAOS=1")
        env.append("TERM=xterm-256color")
        flags = GLib.SpawnFlags.DEFAULT

        def _spawn_done(*_a):
            pass

        ptyf = self._vte.PtyFlags.DEFAULT
        last_err = None
        attempts = [
            (ptyf, wd, argv, env, flags, None, -1, None),           # child_setup, timeout, cancellable
            (ptyf, wd, argv, env, flags, None, -1, None, None),     # + explicit nullable callback
            (ptyf, wd, argv, env, flags, None, -1, None, _spawn_done),
            (ptyf, wd, argv, env, flags, None, None),               # legacy GTK3-era shapes
            (ptyf, wd, argv, env, flags, None, None, None),
        ]
        for args in attempts:
            try:
                term.spawn_async(*args)
                return None
            except (TypeError, ValueError) as ex:
                last_err = ex
        return last_err

    def _apply_colors(self, term):
        """A normal terminal look: black background, light foreground,
        VTE's own default ANSI palette. No custom palette — that is how
        the text went dark last time."""
        from gi.repository import Gdk, Pango
        fg = Gdk.RGBA(); fg.parse("#e8e8e8")
        bg = Gdk.RGBA(); bg.parse("#000000")
        try:
            term.set_colors(fg, bg, [])
            try:
                term.set_scrollback_lines(-1)  # unlimited, like a normal terminal
            except Exception:
                pass
        except Exception:
            pass
        try:
            term.set_font(Pango.font_description_from_string("Monospace 11"))
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
        buf.insert(buf.get_end_iter(),
                   "Sorry Terminal (lite) — real bash underneath.\n"
                   "Type a command and press Enter. ↑/↓ walks history.\n\n")
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(out)

        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry = Gtk.Entry()
        entry.set_hexpand(True)
        entry.set_placeholder_text("Type a command… (try: sorry, hockey, poursyrup)")
        entry.add_css_class("mono")
        entry_row.append(entry)

        filler = Gtk.Box()
        filler.set_hexpand(True)
        entry_row.append(filler)
        entry_row.append(button("Run ⏎", lambda *_: self._send(entry, buf, out, scroller, fd, hist)))
        entry.connect("activate", lambda e: self._send(entry, buf, out, scroller, fd, hist))

        # ↑/↓ walks the command history, so repeat commands aren't retyped.
        hist = {"items": [], "idx": 0}
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._history_nav, entry, hist)

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

        status = base.status_bar(
            (note or "") + " Lite mode: line-by-line input; scroll with the wheel or drag the bar.")

        self.append(scroller)          # output on top…
        self.append(entry_row)         # …input at the bottom like a real terminal
        self.append(status)
        entry.add_controller(keys)

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
            # Only chase the bottom when the user already is there, so
            # reading scrollback isn't yanked out from under them.
            vadj = scroller.get_vadjustment()
            at_bottom = vadj.get_value() + vadj.get_page_size() >= vadj.get_upper() - 48
            if at_bottom:
                out.scroll_mark_onscreen(buf.get_insert())
            return True

        GLib.io_add_watch(fd, GLib.IOCondition.IN, _pump)

    @staticmethod
    def _send(entry, buf, out, scroller, fd, hist):
        line = entry.get_text()
        entry.set_text("")
        if line.strip():
            hist["items"].append(line)
            hist["idx"] = len(hist["items"])
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        except OSError as ex:
            buf.insert(buf.get_end_iter(), "\n(write failed: {})\n".format(ex))
            out.scroll_mark_onscreen(buf.get_insert())

    @staticmethod
    def _history_nav(_ctl, keyval, _code, _state, entry, hist):
        from gi.repository import Gdk
        items = hist["items"]
        if not items:
            return False
        if keyval == Gdk.KEY_Up:
            hist["idx"] = max(0, hist["idx"] - 1)
            entry.set_text(items[hist["idx"]])
            entry.set_position(-1)
            return True
        if keyval == Gdk.KEY_Down:
            hist["idx"] = min(len(items), hist["idx"] + 1)
            entry.set_text(items[hist["idx"]] if hist["idx"] < len(items) else "")
            entry.set_position(-1)
            return True
        return False

    def build(self):
        return self


def build(win, opts=None):
    return Terminal(win, opts=opts)
