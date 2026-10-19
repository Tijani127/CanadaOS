"""Browser app — real internet via WebKit (GTK4 flavour with graceful fallbacks)."""
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from . import base
from .base import app_root, button, row_label


def _load_webkit():
    """Return the GTK4 WebKit module, or None (we degrade politely).

    Note: gir1.2-webkit2-4.x is a GTK3 widget and can never live inside this
    GTK4 shell — loading it is a version mismatch, not a fallback. The GTK4
    engine is WebKitGTK 6.0 (Debian 13 trixie's gir1.2-webkit-6.0).
    """
    global WEB_FAIL_REASON
    import importlib
    candidates = [("WebKit", "6.0")]
    reasons = []
    for name, ver in candidates:
        try:
            import gi as _gi
            _gi.require_version(name, ver)
            mod = importlib.import_module("gi.repository." + name)
            return mod
        except Exception as ex:  # record the true reason for the fallback screen
            reasons.append("{} {}: {}".format(name, ver, ex))
            continue
    WEB_FAIL_REASON = "; ".join(reasons)
    return None


WEB_FAIL_REASON = "not attempted"


HOME_HTML = """<!doctype html><html><head><meta charset='utf-8'>
<style>
body{background:#101418;color:#e8edf2;font-family:sans-serif;display:flex;
align-items:center;justify-content:center;min-height:100vh;margin:0}
main{text-align:center;max-width:560px;padding:28px}
h1{color:#d52b1e;font-size:34px;margin-bottom:4px}
p{color:#9aa4ae}
a{color:#e9b44c;text-decoration:none}
.row{display:inline-block;margin:6px;padding:10px 16px;border-radius:14px;
background:#1c2229;border:1px solid #2b323b}
</style></head><body><main>
<h1>🍁 canadaos://home</h1>
<p>Start page. The real internet is just a URL away.</p>
<div class='row'><a href='https://www.wikipedia.org/wiki/Canada'>Canada (Wikipedia)</a></div>
<div class='row'><a href='https://www.hockeycanada.ca'>Hockey Canada</a></div>
<div class='row'><a href='https://www.timhortons.ca'>Tim Hortons</a></div>
<div class='row'><a href='https://wiki.linuxquestions.org/wiki/Main_Page'>Linux Wiki</a></div>
</main></body></html>"""


class Browser(Gtk.Box):
    def __init__(self, win, opts=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("app-root")
        self.win = win

        self._web_mod = _load_webkit()
        self._web_fail_reason = WEB_FAIL_REASON

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.append(button("◀", lambda *_: self._wrapping("go_back")))
        toolbar.append(button("▶", lambda *_: self._wrapping("go_forward")))
        toolbar.append(button("⟳", lambda *_: self._wrapping("reload")))
        toolbar.append(button("🏠", lambda *_: self.home()))

        self.url = Gtk.Entry()
        self.url.set_hexpand(True)
        self.url.set_placeholder_text("Type a URL… (https://)")
        self.url.connect("activate", self._go)
        toolbar.append(self.url)

        quick = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for label, site in [("Canada wiki", "https://en.wikipedia.org/wiki/Canada"),
                            ("Hockey Canada", "https://www.hockeycanada.ca"),
                            ("Tim Hortons", "https://www.timhortons.ca")]:
            quick.append(button(label, (lambda closure_site=site: (lambda *_: self._load(closure_site)))()))

        if self._web_mod is None:
            fallback = app_root(spacing=10)
            fallback.set_valign(Gtk.Align.CENTER)
            reason = getattr(self, "_web_fail_reason", "no WebKit gir package found")
            fallback.append(row_label("🌐 Browser engine unavailable.", "app-title"))
            fallback.append(row_label(
                "The WebKit engine could not load in this session.\n"
                "Reason: {}\n\n"
                "CanadaOS targets gir1.2-webkit-6.0 (GTK4, Debian 13).\n"
                "If the reason mentions cairo foreign structs, the image is missing\n"
                "python3-gi-cairo.".format(reason),
                "muted-label"))
            self.append(fallback)
            return

        self.web = self._web_mod.WebView()
        try:
            settings = self.web.get_settings()
            settings.set_user_agent("CanadaOSBrowser/1.0 (eager, polite)")
        except AttributeError:
            pass

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self.web)

        self.web.connect("notify::uri", self._sync_url)

        self.append(toolbar)
        self.append(scroller)
        self.append(quick)
        self.append(base.status_bar("🌐 Loaded. Mind the ice."))
        self.home()

    def _wrapping(self, method):
        try:
            getattr(self.web, method)()
        except AttributeError:
            pass

    def _sync_url(self, *a):
        try:
            uri = self.web.get_uri() or ""
            if uri and not uri.startswith("about:"):
                self.url.set_text(uri)
        except Exception:
            pass

    def _load(self, site):
        if not site.startswith(("http://", "https://", "file://")):
            site = "https://" + site
        self.web.load_uri(site)

    def home(self):
        try:
            self.web.load_html(HOME_HTML, "canadaos://home")
        except AttributeError:
            self.web.load_uri("https://en.wikipedia.org/wiki/Canada")

    def _go(self, entry):
        text = entry.get_text().strip()
        if not text:
            return
        if text.startswith("canadaos://home"):
            self.home()
        elif text.startswith(("http://", "https://")):
            self._load(text)
        elif text.startswith("file://") or text.startswith("/"):
            self.web.load_uri("file://" + text.lstrip("/"))
        else:
            # Search politely.
            from urllib.parse import quote_plus
            self._load("https://duckduckgo.com/?q=" + quote_plus(text))


def build(win, opts=None):
    return Browser(win, opts=opts)
