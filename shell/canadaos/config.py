"""CanadaOS user configuration. Stored in ~/.config/canadaos/config.json."""
import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "canadaos"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "dev_mode": False,
    "wallpaper": "midnight-yukon",
}

WALLPAPERS = [
    ("midnight-yukon", "Midnight Yukon"),
    ("forest-night", "Forest Night"),
    ("prairie-night", "Prairie Night"),
]


def load() -> dict:
    try:
        return {**DEFAULTS, **json.loads(CONFIG_FILE.read_text("utf-8"))}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def save(cfg: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), "utf-8")
    except OSError:
        pass


def get(key, default=None):
    return load().get(key, default)


def set_key(key, value):
    cfg = load()
    cfg[key] = value
    save(cfg)
    return cfg


def is_dev_mode() -> bool:
    # CI hook: the app-matrix smoke test flips this so locked apps' real
    # content can be screenshotted, eh.
    if os.environ.get("CANADAOS_FORCE_DEV") in ("1", "true"):
        return True
    return bool(get("dev_mode", False))


def wallpaper() -> str:
    return str(get("wallpaper", "midnight-yukon"))
