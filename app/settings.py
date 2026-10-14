"""User preferences, stored in <data folder>/settings.ini (not the registry, so tests and copies stay separate)."""

from PySide6.QtCore import QSettings

from core import paths
from core.fetcher import DEFAULT_SPEED, SPEEDS

THEMES = (("auto", "Match Windows"), ("light", "Light"), ("dark", "Dark"))
SPEED_CHOICES = (
    ("gentle", "Gentle", "10-20 seconds between pages. Safest. Use for small sites or a site that blocked "
                         "you before. About 240 pages an hour."),
    ("normal", "Normal (recommended)", "5-10 seconds between pages. About 480 pages an hour."),
    ("faster", "Faster", "3-5 seconds between pages. About 900 pages an hour, but a higher chance the site "
                         "blocks this PC. Gleaner never goes faster than one page every 3 seconds."),
)
assert {key for key, _l, _d in SPEED_CHOICES} == set(SPEEDS)


def _store():
    folder = paths.data_home()
    folder.mkdir(parents=True, exist_ok=True)
    return QSettings(str(folder / "settings.ini"), QSettings.Format.IniFormat)


def _get(key, default, allowed=None):
    value = _store().value(key, default)
    if allowed is not None and value not in allowed:
        return default
    return value


def _set(key, value):
    s = _store()
    s.setValue(key, value)
    s.sync()


def theme() -> str:
    return _get("theme", "auto", {k for k, _l in THEMES})


def set_theme(value: str):
    _set("theme", value)


def speed() -> str:
    return _get("speed", DEFAULT_SPEED, set(SPEEDS))


def set_speed(value: str):
    _set("speed", value)


def exports_dir():
    """Where Excel files are written. Empty setting = Documents\\Gleaner (core.paths default)."""
    from pathlib import Path
    value = _get("exports_dir", "")
    return Path(value) if value else paths.exports_dir()


def set_exports_dir(value: str):
    _set("exports_dir", value)


def update_source() -> str:
    """Where to look for new versions: "github:owner/repo" or a path/https URL to latest.json. Empty = off."""
    return str(_get("update_source", "") or "").strip()


def set_update_source(value: str):
    _set("update_source", value.strip())


def auto_update_check() -> bool:
    return str(_get("auto_update_check", "true")).lower() == "true"


def set_auto_update_check(value: bool):
    _set("auto_update_check", "true" if value else "false")


def guide_seen() -> bool:
    return str(_get("guide_seen", "false")).lower() == "true"


def set_guide_seen(value: bool = True):
    _set("guide_seen", "true" if value else "false")
