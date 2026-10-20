"""Sorry Terminal — a normal terminal (real VTE/bash) with Canadian commands."""
import os
import sys

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

        VTE's spawn_async signature has churned between releases: the
        child_setup / timeout / cancellable slots moved around, and None
        in the wrong slot fails with "Argument 9 does not allow None as
        a value" — which for several boots silently downgraded this app
        into the lite terminal without any palette fix ever being seen.
        Instead of guessing argument counts, we read the actual parameter
        list from PyGObject's own introspection and fill exactly those
        named parameters. Returns None on success."""
        from gi.repository import GLib
        wd = os.path.expanduser("~")
        env = ["{}={}".format(k, v) for k, v in os.environ.items()]
        env.append("CANADAOS=1")
        env.append("TERM=xterm-256color")
        ptyf = self._vte.PtyFlags.DEFAULT

        def _spawn_done(*_a):
            pass

        vals = {
            "pty_flags": ptyf,
            "working_directory": wd,
            "argv": argv,
            "envv": env,
            "spawn_flags": GLib.SpawnFlags.DEFAULT,
            "child_setup": None,
            "child_setup_data": None,
            "timeout": -1,
            "cancellable": None,
            "callback": _spawn_done,
        }
        names = self._spawn_param_names(term)
        sys.stderr.write("canadaos: spawn_async params = {}\n".format(names))
        last_err = None
        for drop_callback in (False, True):
            kwargs = {n: v for n, v in vals.items() if n in names}
            if drop_callback:
                kwargs.pop("callback", None)
            if not kwargs:
                break
            try:
                term.spawn_async(**kwargs)
                return None
            except (TypeError, ValueError) as ex:
                last_err = "spawn_async kwargs (callback={}) failed: {}".format(
                    not drop_callback, ex)
        # Last-ditch legacy positional shapes (older vte 2.91-era binding).
        flags = GLib.SpawnFlags.DEFAULT
        for args in (
            (ptyf, wd, argv, env, flags, None, None),
            (ptyf, wd, argv, env, flags, None, None, None),
        ):
            try:
                term.spawn_async(*args)
                return None
            except (TypeError, ValueError) as ex:
                last_err = str(ex)
        return last_err

    @staticmethod
    def _spawn_param_names(term):
        """Parameter names this installed VTE's spawn_async actually takes."""
        import inspect
        names = []
        try:
            sig = inspect.signature(term.spawn_async)
            for p in sig.parameters.values():
                if p.name in ("self",) or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
                    continue
                names.append(p.name)
            if names:
                return names
        except (ValueError, TypeError):
            pass
        # Older PyGObject: parse the first line of __doc__.
        import re
        doc = (getattr(term.spawn_async, "__doc__", "") or "")
        m = re.search(r"spawn_async\(([^)]*)\)", doc.split("\n", 1)[0])
        if m:
            for raw in m.group(1).split(","):
                raw = raw.strip()
                raw = raw.split(":")[0].split("=")[0].strip()
                if raw in ("", "self", "user_data", "*user_data"):
                    continue
                names.append(raw)
        return names

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
