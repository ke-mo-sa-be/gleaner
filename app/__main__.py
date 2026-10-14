"""Start the desktop app: py -m app"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from app import settings, style
from app.main_window import MainWindow
from core import paths
from core.recipe import RecipeError, load_recipe
from core.store import Store

log = logging.getLogger("app")


def bundled_recipes_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "recipes"


def setup_logging():
    folder = paths.data_home() / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(folder / "app.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def seed_example_recipes(store):
    """Import shipped example recipes once, on first start (docs/DATABASE.md section 12)."""
    marker = paths.data_home() / ".examples-imported"
    if marker.exists():
        return
    for path in sorted(bundled_recipes_dir().glob("*.json")):
        try:
            recipe = load_recipe(path)
            if store.find_recipe(recipe.name) is None:
                store.save_recipe(recipe)
        except (RecipeError, OSError):
            log.exception("could not import example recipe %s", path.name)
    marker.touch()


def main():
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Gleaner")
    style.apply(app, settings.theme())

    def on_error(exc_type, exc, tb):
        log.error("unhandled error", exc_info=(exc_type, exc, tb))
        QMessageBox.critical(None, "Gleaner", "Something went wrong. Details are in the log file:\n"
                             f"{paths.data_home() / 'logs' / 'app.log'}")

    sys.excepthook = on_error

    store = Store(paths.db_path())
    interrupted = store.mark_interrupted()
    if interrupted:
        log.info("%s run(s) marked interrupted after an unclean exit", interrupted)
    seed_example_recipes(store)

    window = MainWindow(store)
    window.resize(1360, 860)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
