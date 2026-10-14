"""Where Gleaner keeps its files (docs/ARCHITECTURE.md section 3)."""

import os
from pathlib import Path


def data_home() -> Path:
    override = os.environ.get("GLEANER_HOME")
    if override:
        return Path(override)
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Gleaner"


def db_path() -> Path:
    return data_home() / "collector.db"


def exports_dir() -> Path:
    override = os.environ.get("GLEANER_HOME")
    if override:
        return Path(override) / "exports"
    return Path.home() / "Documents" / "Gleaner"
