"""Main window: sidebar navigation between Library, Recipe builder, Run, Guide and Settings."""

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (QHBoxLayout, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QStackedWidget, QWidget)

from app import __version__, settings
from app.builder_view import BuilderView
from app.help_view import HelpView
from app.library_view import LibraryView
from app.run_view import RunView
from app.settings_view import SettingsView, open_update
from app.tasks import run_task
from core import updates

LIBRARY, BUILDER, RUN, GUIDE, SETTINGS = range(5)
SECTIONS = ("Library", "Recipe builder", "Run", "Guide", "Settings")


class MainWindow(QMainWindow):
    def __init__(self, store, check_updates=True):
        super().__init__()
        self.setWindowTitle(f"Gleaner {__version__}")
        self.setMinimumSize(1100, 700)
        self.store = store

        self.library = LibraryView(store)
        self.builder = BuilderView(store)
        self.run_view = RunView(store)
        self.help_view = HelpView()
        self.settings_view = SettingsView()

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for text in SECTIONS:
            item = QListWidgetItem(text)
            item.setSizeHint(QSize(190, 40))
            self.nav.addItem(item)
        self.nav.setFixedWidth(190)
        self.nav.setWordWrap(False)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setAccessibleName("Sections")
        self.stack = QStackedWidget()
        for view in (self.library, self.builder, self.run_view, self.help_view, self.settings_view):
            self.stack.addWidget(view)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.nav)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.library.edit_requested.connect(self.edit_recipe)
        self.library.run_requested.connect(self.run_recipe)
        self.builder.saved.connect(self._recipe_saved)
        self.run_view.run_finished.connect(self.library.refresh)
        for view in (self.library, self.builder, self.settings_view):
            view.help_requested.connect(self.show_help)
        self.nav.setCurrentRow(LIBRARY)

        if check_updates and settings.auto_update_check():
            QTimer.singleShot(3000, self._check_updates)

    def show_help(self, key):
        self.help_view.show_section(key)
        self.nav.setCurrentRow(GUIDE)

    def edit_recipe(self, recipe_id):
        if not self.builder.confirm_discard():
            return
        if recipe_id is None:
            self.builder.new_recipe()
        else:
            self.builder.load_recipe(recipe_id)
        self.nav.setCurrentRow(BUILDER)

    def run_recipe(self, recipe_id):
        if self.run_view.running and self.run_view.recipe_id != recipe_id:
            QMessageBox.information(self, "A run is in progress",
                                    "Another recipe is running. Stop it first, or wait until it finishes.")
        else:
            self.run_view.set_recipe(recipe_id)
        self.nav.setCurrentRow(RUN)

    def _recipe_saved(self, _recipe_id):
        self.library.refresh()
        self.statusBar().showMessage("Recipe saved.", 5000)

    def _check_updates(self):
        source = settings.update_source() or updates.DEFAULT_SOURCE
        # Quiet on failure: offline PCs shouldn't see an error every start. Settings > Check now shows details.
        run_task(updates.check, source, __version__, on_done=self._update_found, on_failed=lambda _m: None)

    def _update_found(self, info):
        if info is not None:
            self.library.show_update(info, lambda: open_update(info))
            self.statusBar().showMessage(f"Gleaner {info.version} is available. See the Library.", 15000)

    def closeEvent(self, event):
        if self.run_view.running:
            answer = QMessageBox.question(
                self, "A run is in progress",
                "Close Gleaner? The run stops now and continues from where it stopped next time you press Start.")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.run_view.request_stop()
        if not self.builder.confirm_discard():
            event.ignore()
            return
        event.accept()
