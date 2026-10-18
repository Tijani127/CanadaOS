"""App registry — the launcher's brain, eh."""
from dataclasses import dataclass, field
from typing import Callable, Optional

from .base import lock_content  # noqa: F401
from .paint import Paint, build as build_paint           # noqa: F401
from .notepad import build as build_notepad              # noqa: F401
from .browser import build as build_browser              # noqa: F401
from .terminal import build as build_terminal            # noqa: F401
from .settings import build as build_settings            # noqa: F401
from .files import build as build_files                  # noqa: F401
from .hockey import build as build_hockey                # noqa: F401
from .syrup import build as build_syrup                  # noqa: F401


@dataclass
class AppInfo:
    app_id: str
    title: str
    emoji: str
    factory: Callable
    width: int = 900
    height: int = 620
    dev_only: bool = False
    desc: str = ""


def _make_factory(info):
    """Wrap a normal app factory so locked apps show the Dev-Mode notice."""
    def factory(win, opts=None):
        if info.dev_only and not _is_dev():
            from .base import lock_content
            return lock_content(win, info)
        return info.factory(win, opts or {})
    return factory


APPS = [
    AppInfo("paint", "Paint", "🎨", build_paint, 940, 640, False,
            "Paint with Canadian colours, eh."),
    AppInfo("notepad", "Notepad", "🗒️", build_notepad, 820, 580, False,
            "Plain text notes. No dev perks, eh."),
    AppInfo("browser", "Browser", "🌐", build_browser, 1100, 720, False,
            "Real internet via WebKit."),
    AppInfo("files", "Files", "🗃️", build_files, 940, 620, False,
            "Folders are polite places."),
    AppInfo("hockey", "Hockey Arena", "🏒", build_hockey, 1080, 660, False,
            "Shootout simulator + NHLe scores."),
    AppInfo("settings", "Settings", "⚙️", build_settings, 760, 620, False,
            "Configure CanadaOS, eh."),
    AppInfo("terminal", "Sorry Terminal", "💻", build_terminal, 900, 580, True,
            "Real bash with politeness layer."),
    AppInfo("syrup", "Maple Syrup Editor", "🍁", build_syrup, 1040, 700, True,
            "Syntax highlighting for .maple code."),
]


def get_app(app_id):
    for info in APPS:
        if info.app_id == app_id:
            return info
    return None


def _is_dev():
    from .. import config
    return config.is_dev_mode()


def factory_for(info):
    """Return the (Dev-Mode aware) callable the desktop calls to build an app."""
    def call(win, opts=None):
        if info.dev_only and not _is_dev():
            from .base import lock_content
            return lock_content(win, info)
        return info.factory(win, opts or {})
    return call
