"""Update now: download the new installer (checked against its published SHA-256), then let it replace
Gleaner and open it again. Recipes, collected data and Excel files are kept (they live outside the app folder).
"""

import logging
import subprocess
import sys

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from app.tasks import run_task
from app.widgets import open_path
from core import paths, updates

log = logging.getLogger(__name__)

# Inno Setup: no questions, close Gleaner if it is still open, then start it again (gleaner.iss "relaunch").
INSTALL_ARGS = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/RELAUNCH=1"]


def can_install() -> bool:
    """Only an installed Gleaner can replace itself; when run from source, Update now opens the download."""
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def open_update(info):
    """Fallback: open the installer's download link in the browser, or the file in a shared folder."""
    if info.url.lower().startswith("https://"):
        QDesktopServices.openUrl(QUrl(info.url))
    else:
        open_path(info.url)


def action_label(info) -> str:
    return "Update now" if can_install() and info.can_download else "Download"


def launch_installer(path):
    """Start the installer on its own, so it keeps running after Gleaner closes."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(path), *INSTALL_ARGS], creationflags=flags, close_fds=True)


class _Progress(QObject):
    changed = Signal(int, int)


class Updater(QObject):
    """update(info) runs the whole flow. ready_to_quit() (from the main window) checks nothing is lost and
    returns True when Gleaner may close; quit() closes it."""

    def __init__(self, parent, ready_to_quit, quit):
        super().__init__(parent)
        self.window = parent
        self.ready_to_quit = ready_to_quit
        self.quit = quit
        self.busy = False
        self._cancelled = False
        self._progress = _Progress()
        self._progress.changed.connect(self._show_progress)
        self.dialog = None

    def update(self, info):
        if not (can_install() and info.can_download):
            open_update(info)
            return
        if self.busy:
            return
        self.busy, self._cancelled = True, False
        self.dialog = QProgressDialog(f"Downloading Gleaner {info.version}...", "Cancel", 0, 100, self.window)
        self.dialog.setWindowTitle("Update Gleaner")
        self.dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.dialog.setMinimumDuration(0)
        self.dialog.canceled.connect(self._cancel)
        self.dialog.setValue(0)
        run_task(updates.download, info, paths.data_home() / "updates", self._report,
                 on_done=lambda path: self._downloaded(info, path), on_failed=self._failed)

    def _report(self, done, total):  # download thread
        if self._cancelled:
            raise updates.UpdateError("The update was cancelled.")
        self._progress.changed.emit(done, total)

    def _show_progress(self, done, total):
        if self.dialog and total:
            self.dialog.setValue(min(99, int(done * 100 / total)))
            self.dialog.setLabelText(f"Downloading... {done // 1_000_000} of {total // 1_000_000} MB")

    def _cancel(self):
        self._cancelled = True

    def _close_dialog(self):
        if self.dialog:
            self.dialog.canceled.disconnect(self._cancel)
            self.dialog.close()
            self.dialog = None
        self.busy = False

    def _failed(self, message):
        cancelled = self._cancelled
        self._close_dialog()
        if not cancelled:
            QMessageBox.warning(self.window, "Update Gleaner", message)

    def _downloaded(self, info, path):
        self._close_dialog()
        answer = QMessageBox.question(
            self.window, "Update Gleaner",
            f"Gleaner {info.version} is ready to install.\n\nGleaner will close, update and open again (about a "
            "minute). Your recipes, collected data and Excel files are kept.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Ok)
        if answer != QMessageBox.StandardButton.Ok or not self.ready_to_quit():
            return
        try:
            launch_installer(path)
        except OSError:
            log.exception("could not start the installer")
            QMessageBox.warning(self.window, "Update Gleaner",
                                "Windows didn't let Gleaner start the installer. It is saved here; run it "
                                f"yourself:\n{path}")
            return
        self.quit()
