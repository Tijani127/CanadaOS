"""Maple Syrup editor — the .maple editor with a real runner."""
import contextlib
import io
import re
import sys

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from . import base
from .base import button, row_label

KEYWORDS = [
    "tap", "pour", "harvest", "boil", "sorry", "thanks", "please",
    "import", "def", "return", "for", "while", "in", "if", "else", "elif",
    "try", "catch", "raise",
]
BUILTINS = ["pour", "tap", "warm", "cool", "print", "grade_a", "evaporate"]

TAG_DEFS = [
    ("comment", "#9aa4ae", None),
    ("string", "#7ec142", False),
    ("keyword", "#d52b1e", True),
    ("number", "#e9b44c", None),
    ("builtin", "#c792ea", None),
    ("bracket", "#5db6d7", None),
]

SAMPLE = """# First .maple program. Welcome to the sugar bush.
import syrup

def make_syrup(size, grade):
    if grade < "a":
        sorry # not our finest batch
        return size / 2
    boil("sap", temp=104)
    tap("maple trees")
    return pour(grade)

make_syrup(10, "amber")
"""

PATTERN = re.compile(
    r"(#.*$|\"[^\"]*\"|'[^']*'|\b(?:{})\b|\b\d+(?:\.\d+)?\b|[{}\[\]()<>])".format(
        "|".join(KEYWORDS), re.escape("{}[]()<>")))

SAFE_BUILTINS = {
    "print": print, "range": range, "len": len,
    "min": min, "max": max, "abs": abs, "round": round,
    "str": str, "int": int, "float": float,
}


class Syrup(Gtk.Box):
    def __init__(self, win, opts=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("app-root")
        self.win = win
        self.path = None
        self._highlight_soon_id = None

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title = row_label("Maple Syrup Editor", "app-title")
        title.set_hexpand(True)
        toolbar.append(title)
        toolbar.append(button("New Sample 🍁", lambda *_: self.load_sample()))
        toolbar.append(button("Open 📂", lambda *_: self.open_file()))
        toolbar.append(button("Save 💾", lambda *_: self.save()))
        toolbar.append(button("Run ▶", lambda *_: self.run(), "app-tile"))
        toolbar.append(button("Pour (Lint) 🥞", lambda *_: self.lint()))
        toolbar.append(button("Help ❔", lambda *_: self.help()))

        self.buffer = Gtk.TextBuffer()
        self.buffer.create_tag("comment", foreground="#9aa4ae")
        self.buffer.create_tag("string", foreground="#7ec142")
        self.buffer.create_tag("keyword", foreground="#d52b1e", weight=700)
        self.buffer.create_tag("number", foreground="#e9b44c")
        self.buffer.create_tag("builtin", foreground="#c792ea")
        self.buffer.create_tag("bracket", foreground="#5db6d7")

        self.view = Gtk.TextView(buffer=self.buffer)
        self.view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.view.set_monospace(True)
        self.view.set_vexpand(True)
        self.view.add_css_class("mono")

        self.gutter = Gtk.Label(label="1")
        self.gutter.add_css_class("gutter")
        self.gutter.set_halign(Gtk.Align.START)
        self.gutter.set_valign(Gtk.Align.START)
        self.gutter.set_margin_top(4)

        editor_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        editor_row.set_margin_start(6)
        editor_row.append(self.gutter)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_hexpand(True)
        scroller.set_child(self.view)
        editor_row.append(scroller)

        self.status = base.status_bar("Maple editor. Ln 1, Col 1.")

        self.append(toolbar)
        self.append(editor_row)
        self.append(self.status)

        self.buffer.connect("changed", self._on_changed)
        self.buffer.connect("notify::cursor-position", self._on_cursor)

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self.view.add_controller(key)

        self.load_sample()
        if opts and opts.get("path"):
            self.load_path(opts["path"])

    def load_sample(self):
        self.buffer.set_text(SAMPLE)
        self.path = None
        self.status.set_text("Fresh sample loaded. Press Run ▶ to see it flow.")

    def open_file(self):
        base.choose_open_file(self.win, lambda p: self.load_path(p) if p else None)

    def load_path(self, path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                self.buffer.set_text(fh.read())
            self.path = path
            self.status.set_text("Loaded {}".format(path))
        except (OSError, UnicodeDecodeError) as ex:
            base.info_dialog(self.win, "Sorry", "Couldn't load:\n{}".format(ex))

    def save(self):
        def done(path):
            if not path:
                return
            if not path.endswith(".maple"):
                path += ".maple"
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(self._text())
                self.path = path
                self.status.set_text("Saved to {}".format(path))
            except OSError as ex:
                base.info_dialog(self.win, "Sorry", "Save failed:\n{}".format(ex))
        base.choose_save_file(self.win, done, suggested="syrup.maple")

    def _text(self):
        start, end = self.buffer.get_bounds()
        return self.buffer.get_text(start, end, False)

    def _on_changed(self, buf):
        if self._highlight_soon_id is not None:
            GLib.source_remove(self._highlight_soon_id)
        self._highlight_soon_id = GLib.timeout_add(120, self._highlight)
        self._gutter()

    def _on_cursor(self, buf, pspec):
        it = buf.get_iter_at_mark(buf.get_insert())
        self.status.set_text("Ln {}, Col {}".format(it.get_line() + 1, it.get_line_offset() + 1))

    def _highlight(self):
        self._highlight_soon_id = None
        buf = self.buffer
        start, end = buf.get_bounds()
        for name in ("comment", "string", "keyword", "number", "builtin", "bracket"):
            buf.remove_tag_by_name(name, start, end)
        text = self._text()
        for match in PATTERN.finditer(text):
            span = match.span()
            chunk = match.group(0)
            tag = ("comment" if chunk.startswith("#")
                   else "string" if chunk[0] in "\"'"
                   else "bracket" if chunk in "{}[]()<>"
                   else "number" if chunk[:1].isdigit()
                   else "keyword")
            if tag == "keyword" and chunk in BUILTINS:
                tag = "builtin"
            s = buf.get_iter_at_offset(span[0])
            e = buf.get_iter_at_offset(span[1])
            buf.apply_tag_by_name(tag, s, e)
        return False

    def _gutter(self):
        n = self.buffer.get_line_count()
        self.gutter.set_text("\n".join(str(i + 1) for i in range(n)))

    def _on_key(self, ctl, keyval, keycode, state):
        from gi.repository import Gdk
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._smart_newline()
            return True
        return False

    def _smart_newline(self):
        buf = self.buffer
        it = buf.get_iter_at_mark(buf.get_insert())
        line_start = it.copy()
        line_start.set_line_offset(0)
        line_text = buf.get_text(line_start, it, True)
        indent = " " * (len(line_text) - len(line_text.lstrip(" ")))
        extra = "    " if line_text.rstrip().endswith(":") else ""
        buf.insert(it, "\n" + indent + extra, -1)

    # ---------- the runner ----------
    def _transpile(self):
        """Maple subset → Python via small call-name rewrites. The newline
        structure is preserved, so a generated line n corresponds to source
        line n-1 (one glue preamble line on top)."""
        src = self._text()
        body = []
        for line in src.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("import "):
                body.append("")  # keep line numbering stable
                continue
            m = re.match(r"^(sorry|thanks|please)\b\s*(?:#.*)?$", s)
            if m and "(" not in s:
                body.append("__log('{}')".format(m.group(1)))
                continue
            t = line
            t = re.sub(r"\b[sS]orry\s*\(", "__log(", t)
            t = re.sub(r"\b[tT]ap\s*\(", "__log(", t)
            t = re.sub(r"\b[tT]hanks\s*\(|\b[pP]lease\s*\(", "__log(", t)
            t = re.sub(r"\b[bB]oil\s*\(", "__boil(", t)
            t = re.sub(r"\b[pP]our\s*\(", "__pour(", t)
            t = re.sub(r"\bcatch\b", "except", t)
            t = re.sub(r"\bharvest\b", "pass", t)  # polite no-op
            body.append(t)
        code = "\n".join(["# generated glue — reverse-map line numbers",
                          *body])
        return code, src

    def _src_line(self, src_lines, maple_lineno):
        """Map a <maple>-compile line number back to the source text."""
        idx = (maple_lineno or 0) - 2  # skip 1 glue line, 1-based → 0-based
        if 0 <= idx < len(src_lines):
            return idx + 1, src_lines[idx].strip()
        return None, ""

    def run(self):
        """Run the .maple program in a restricted namespace."""
        code, src = self._transpile()
        src_lines = src.splitlines()
        log = []

        def __log(*parts):
            log.append(" ".join(str(p) for p in parts))

        def __boil(item="sap", temp=104):
            msg = "Boiling {} at {}°C — getting thicker…".format(item, temp)
            log.append(msg)
            return msg

        def __pour(grade="amber"):
            msg = "Pouring {}-grade syrup 🍁".format(grade)
            log.append(msg)
            return msg

        ns = {"__log": __log, "__boil": __boil, "__pour": __pour,
              "__name__": "__maple__"}
        ns["__builtins__"] = dict(SAFE_BUILTINS)
        try:
            compiled = compile(code, "<maple>", "exec")
        except SyntaxError as ex:
            src_no, snippet = self._src_line(src_lines, ex.lineno)
            where = ("line {}: {} | {}".format(src_no, snippet, ex.msg)
                     if src_no else "{}: {}".format(type(ex).__name__, ex))
            base.info_dialog(
                self.win, "Run ▶ — syntax error",
                "{}\n\nIndentation matters: block lines under a def/if/for/while\n"
                "use the same indent, and spaces not tabs.".format(where))
            return
        try:
            with io.StringIO() as buf:
                with contextlib.redirect_stdout(buf):
                    exec(compiled, ns)
                captured = buf.getvalue()
            report = "\n".join([*log, *([captured.rstrip()] if captured else [])]).strip()
            base.info_dialog(self.win, "Run ▶ output",
                             report or "(Program ran clean — no output.)")
            self.status.set_text("Ran {} lines of maple.".format(len(src_lines)))
        except Exception as ex:
            tb = sys.exc_info()[2]
            src_no, snippet = self._src_line(src_lines, tb.tb_lineno if tb else None)
            where = ("line {}: {} | ".format(src_no, snippet) if src_no else "")
            base.info_dialog(
                self.win, "Run ▶ error",
                "{}{}: {}\n\nThe program stopped mid-run; maple speaks\n"
                "def / if / for / while / return, plus calls like\n"
                "boil(\"sap\", temp=104), tap(\"…\"), pour(grade).".format(where, type(ex).__name__, ex))

    def lint(self):
        text = self._text()
        ob, cb = text.count("{"), text.count("}")
        sb, cb2 = text.count("["), text.count("]")
        probs = []
        if ob != cb:
            probs.append("Unbalanced braces (open {} close {}).".format(ob, cb))
        if sb != cb2:
            probs.append("Unbalanced brackets (open {} close {}).".format(sb, cb2))
        if "\t" in text:
            probs.append("Tab character found — this project indents with 4 spaces.")
        if "hoser" in text:
            probs.append("The word 'hoser' found. Please keep it friendly.")

        # A real parse: the same transpile the runner uses, compiled (not
        # executed). A syntax error is a syntax error — no Grade A for you.
        code, _src = self._transpile()
        try:
            compile(code, "<maple>", "exec")
        except SyntaxError as ex:
            src_no, snippet = self._src_line(text.splitlines(), ex.lineno)
            probs.append("Grammatical trouble: {} — {}".format(
                "line {}: {}".format(src_no, snippet) if src_no else "unparsed",
                ex.msg))

        out = ("🌳 Sugar bush report:\n" +
               ("\n".join(probs) if probs else
                "Everything balanced. Pure 100% Grade A."))
        base.info_dialog(self.win, "Pour Report", out)

    def help(self):
        base.info_dialog(
            self.win, "Maple language help",
            "A tiny Canadian scripting language:\n"
            "  # comment\n"
            "  def make_syrup(size, grade):\n"
            "      boil(\"sap\", temp=104)\n"
            "      return pour(grade)\n"
            "Calls: boil(item, temp) · tap(\"msg\") · pour(grade) · sorry\n"
            "Bare 'sorry'/'thanks'/'please' on a line = just a note in the log.\n"
            "Python-style if/for/while/def/return all work.\n"
            "Press Run ▶ to execute. Files: .maple")


def build(win, opts=None):
    return Syrup(win, opts=opts)
