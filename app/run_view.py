"""Run view: start, pause, stop a recipe and show progress in plain language (UX Flows 4-6)."""

import logging
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QMessageBox, QPlainTextEdit, QProgressBar, QSpinBox, QVBoxLayout,
                               QWidget)

from app import settings
from app.widgets import Banner, button, label, open_path
from core import paths
from core.export import export_workbook
from core.fetcher import Fetcher, speed_delays
from core.runner import RunControl, run_recipe
from core.store import Store

log = logging.getLogger(__name__)

OUTCOMES = {
    "done": ("success", "Done."),
    "stopped": ("warning", "Stopped. Press Start to continue where it stopped."),
    "blocked": ("error", "The site stopped responding to us normally (it may have blocked this PC). "
                         "The run has been stopped. Don't run this recipe again today. Tell your manager."),
    "disallowed": ("error", "This site's robots rules don't allow collecting these pages. Gleaner stopped."),
    "network_error": ("warning", "Network problem. Check the internet connection, then press Start to continue."),
    "no_items": ("warning", "No items found on the start page. The site may have changed. Edit the recipe."),
    "error": ("error", "Something went wrong. Details are in the log file."),
}


class RunWorker(QObject):
    progress = Signal(object)
    finished = Signal(dict)

    def __init__(self, recipe_id, control, max_pages, max_records, speed="normal", exports_dir=None):
        super().__init__()
        self.recipe_id = recipe_id
        self.control = control
        self.max_pages = max_pages
        self.max_records = max_records
        self.speed = speed
        self.exports_dir = exports_dir or paths.exports_dir()

    def run(self):
        store = Store(paths.db_path())
        outcome = {"status": "error", "note": "", "records": 0}
        try:
            min_delay, max_delay = speed_delays(self.speed)
            fetcher = Fetcher(store, min_delay=min_delay, max_delay=max_delay)
            result = run_recipe(store, self.recipe_id, fetcher, self.control, self.progress.emit,
                                self.max_pages, self.max_records)
            outcome = {"status": result.status, "note": result.note, "records": result.records}
            path, ready, review = export_workbook(self.exports_dir, store.get_recipe(self.recipe_id),
                                                  store.records(self.recipe_id), store.runs(self.recipe_id))
            outcome.update(path=path, ready=ready, review=review)
        except Exception as exc:  # thread boundary
            log.exception("run failed")
            outcome["note"] = str(exc)
        finally:
            store.close()
            self.finished.emit(outcome)


class RunView(QWidget):
    run_finished = Signal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.setObjectName("view")
        self.store = store
        self.recipe_id = None
        self.control = None
        self.worker = None
        self.started_at = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        self.title = label("Run a recipe", "h1")
        layout.addWidget(self.title)
        self.subtitle = label("Pick a recipe in the Library and click Run.", "hint", wrap=True)
        layout.addWidget(self.subtitle)

        limits = QHBoxLayout()
        limits.addWidget(label("Stop after"))
        self.max_records = QSpinBox()
        self.max_records.setRange(0, 1_000_000)
        self.max_records.setSpecialValueText("all records")
        self.max_records.setSingleStep(50)
        limits.addWidget(self.max_records)
        limits.addWidget(label("  and"))
        self.max_pages = QSpinBox()
        self.max_pages.setRange(0, 100_000)
        self.max_pages.setSpecialValueText("all pages")
        limits.addWidget(self.max_pages)
        limits.addWidget(label("    Speed"))
        self.speed = QComboBox()
        for key, text, _desc in settings.SPEED_CHOICES:
            self.speed.addItem(text, key)
        self.speed.setAccessibleName("Speed")
        self.speed.currentIndexChanged.connect(self._speed_changed)
        limits.addWidget(self.speed)
        limits.addStretch(1)
        layout.addLayout(limits)

        bar = QHBoxLayout()
        self.start_btn = button("Start", "primary")
        self.pause_btn = button("Pause")
        self.stop_btn = button("Stop", "danger")
        for b in (self.start_btn, self.pause_btn, self.stop_btn):
            bar.addWidget(b)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        layout.addWidget(self.progress)
        self.counters = label("", "hint")
        layout.addWidget(self.counters)

        self.banner = Banner()
        layout.addWidget(self.banner)

        layout.addWidget(label("What's happening", "h2"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.log, 1)
        self.speed_hint = label("", "hint", wrap=True)
        layout.addWidget(self.speed_hint)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.start_btn.clicked.connect(self.start)
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.stop_btn.clicked.connect(self._stop)
        self.pages = self.records = 0
        self._select_speed(settings.speed())
        self._set_running(False)

    def _select_speed(self, key):
        index = self.speed.findData(key)
        self.speed.setCurrentIndex(index if index >= 0 else self.speed.findData("normal"))
        self._speed_changed()

    def _speed_changed(self, _index=None):
        desc = next(d for k, _t, d in settings.SPEED_CHOICES if k == self.speed.currentData())
        self.speed_hint.setText(desc + " The pause between pages is on purpose: it keeps the website "
                                "from being overloaded and this PC from being blocked.")

    @property
    def running(self):
        return self.worker is not None

    def set_recipe(self, recipe_id):
        if self.running:
            return
        self.recipe_id = recipe_id
        recipe = self.store.get_recipe(recipe_id)
        self.title.setText(recipe.name)
        count = self.store.record_count(recipe_id)
        self.subtitle.setText(f"{count:,} records collected so far. Start continues where the last run stopped."
                              if count else "Not run yet.")
        self.banner.hide()
        self.log.clear()
        self.counters.setText("")
        self._select_speed(settings.speed())
        self._set_running(False)

    def start(self):
        if self.recipe_id is None or self.running:
            return
        last = self.store.last_run(self.recipe_id)
        if last and last["status"] == "blocked":
            answer = QMessageBox.warning(
                self, "Last run was blocked",
                f"The last run was blocked by the site on {last['started_at'][:10]}.\n\n"
                "Running again can get this PC banned. Run anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.banner.hide()
        self.log.clear()
        self.pages = self.records = 0
        self.control = RunControl()
        self.worker = RunWorker(self.recipe_id, self.control, self.max_pages.value(), self.max_records.value(),
                                self.speed.currentData(), settings.exports_dir())
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.started_at = time.monotonic()
        self._append("Starting. Checking the site's robots rules first.")
        self._set_running(True)
        threading.Thread(target=self.worker.run, daemon=True).start()

    def request_stop(self):
        """Used when the app closes during a run; the run resumes from the cache next time."""
        if self.control:
            self.control.stop()

    def _toggle_pause(self):
        if not self.control:
            return
        if self.control.paused:
            self.control.resume()
            self.pause_btn.setText("Pause")
            self._append("Resumed.")
        else:
            self.control.pause()
            self.pause_btn.setText("Resume")
            self._append("Pausing after the current page...")

    def _stop(self):
        if self.control:
            self.control.stop()
            self.stop_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self._append("Stopping after the current page...")

    def _on_progress(self, p):
        self.pages, self.records = p.pages, p.records
        self._append(p.message)
        self._tick()

    def _on_finished(self, outcome):
        self.worker = None
        self.control = None
        self.timer.stop()
        self._set_running(False)
        self.pause_btn.setText("Pause")
        kind, title = OUTCOMES.get(outcome["status"], OUTCOMES["error"])
        details = ""
        actions = []
        if outcome.get("path"):
            path = outcome["path"]
            title = f"{title} {outcome['records']:,} new records this run."
            details = f"Excel: {outcome['ready']:,} ready, {outcome['review']:,} need review. {path}"
            actions = [("Open Excel", lambda: open_path(path)), ("Open folder", lambda: open_path(path.parent))]
        if outcome["status"] not in ("done", "stopped") and outcome.get("note"):
            details = (details + "\n" if details else "") + f"Details: {outcome['note']}"
        self.banner.show_message(kind, title, details, actions)
        self._append(title)
        self.run_finished.emit()

    def _append(self, text):
        self.log.appendPlainText(f"{time.strftime('%H:%M:%S')}  {text}")

    def _tick(self):
        if self.started_at is None:
            return
        elapsed = int(time.monotonic() - self.started_at)
        self.counters.setText(f"Pages {self.pages:,}   Records {self.records:,}   "
                              f"Time {elapsed // 3600:d}:{elapsed // 60 % 60:02d}:{elapsed % 60:02d}")

    def _set_running(self, running):
        self.start_btn.setEnabled(not running and self.recipe_id is not None)
        self.pause_btn.setEnabled(running)
        self.stop_btn.setEnabled(running)
        self.max_records.setEnabled(not running)
        self.max_pages.setEnabled(not running)
        self.speed.setEnabled(not running)
        self.progress.setRange(0, 0 if running else 1)
        if running:
            self.timer.start()
