"""Main window: sidebar navigation between Library, Recipe builder, Run, Guide and Settings."""

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from app import __version__, settings, style
from app.builder_view import BuilderView
from app.help_view import HelpView
from app.library_view import LibraryView
from app.run_view import RunView
from app import updater
from app.settings_view import SettingsView
from app.tasks import run_task
from app.widgets import glyph_icon
from core import updates

LIBRARY, BUILDER, RUN, GUIDE, SETTINGS = range(5)
SECTIONS = ("Library", "Recipe builder", "Run", "Guide", "Settings")
SECTION_ICONS = ("library", "builder", "run", "guide", "settings")
NAV_WIDE, NAV_NARROW = 190, 52
THEME_ORDER = ("auto", "light", "dark")
THEME_NAMES = {"auto": "Match Windows", "light": "Light", "dark": "Dark"}


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
        self._updater = None  # made when an update starts
        self._updating = False
        self.update_box = None

        self.nav_collapsed = settings.nav_collapsed()
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for text in SECTIONS:
            item = QListWidgetItem(text)
            item.setSizeHint(QSize(NAV_WIDE, 40))
            item.setData(Qt.ItemDataRole.AccessibleTextRole, text)
            self.nav.addItem(item)
        self.nav.setIconSize(QSize(20, 20))
        self.nav.setWordWrap(False)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setAccessibleName("Sections")

        # Sidebar: collapse button, sections, and the theme button at the bottom (visible on every screen).
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)  # paint the stylesheet border
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(0, 0, 1, 0)  # keep the right border visible beside the buttons
        side.setSpacing(0)
        self.collapse_btn = QToolButton()
        self.collapse_btn.setObjectName("navButton")
        self.collapse_btn.setIconSize(QSize(20, 20))
        self.collapse_btn.clicked.connect(self.toggle_nav)
        side.addWidget(self.collapse_btn)
        side.addWidget(self.nav, 1)
        self.theme_btn = QToolButton()
        self.theme_btn.setObjectName("navButton")
        self.theme_btn.setIconSize(QSize(20, 20))
        self.theme_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.theme_btn.clicked.connect(self.cycle_theme)
        side.addWidget(self.theme_btn)
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, activated=self.cycle_theme)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.toggle_nav)
        style.theme_changed.changed.connect(self._render_sidebar)
        self.stack = QStackedWidget()
        for view in (self.library, self.builder, self.run_view, self.help_view, self.settings_view):
            self.stack.addWidget(view)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.currentRowChanged.connect(lambda _row: self._render_sidebar())
        self.library.edit_requested.connect(self.edit_recipe)
        self.library.run_requested.connect(self.run_recipe)
        self.builder.saved.connect(self._recipe_saved)
        self.run_view.run_finished.connect(self.library.refresh)
        for view in (self.library, self.builder, self.settings_view):
            view.help_requested.connect(self.show_help)
        self.settings_view.update_requested.connect(self.update_now)
        self.nav.setCurrentRow(LIBRARY)
        self._render_sidebar()

        if check_updates and settings.auto_update_check():
            QTimer.singleShot(3000, self._check_updates)

    # ---- sidebar -----------------------------------------------------------------------------

    def toggle_nav(self):
        self.nav_collapsed = not self.nav_collapsed
        settings.set_nav_collapsed(self.nav_collapsed)
        self._render_sidebar()

    def cycle_theme(self):
        current = style.theme() if style.theme() in THEME_ORDER else "auto"
        key = THEME_ORDER[(THEME_ORDER.index(current) + 1) % len(THEME_ORDER)]
        settings.set_theme(key)
        style.apply(QApplication.instance(), key)  # theme_changed redraws the sidebar and Settings
        self.statusBar().showMessage(f"Theme: {THEME_NAMES[key]}", 3000)

    def _render_sidebar(self):
        narrow = self.nav_collapsed
        width = NAV_NARROW if narrow else NAV_WIDE
        self.sidebar.setFixedWidth(width)
        for row, (text, icon) in enumerate(zip(SECTIONS, SECTION_ICONS)):
            item = self.nav.item(row)
            item.setText("" if narrow else text)
            item.setToolTip(text if narrow else "")
            item.setIcon(glyph_icon(icon, "PRIMARY" if row == self.nav.currentRow() else "MUTED"))
            item.setSizeHint(QSize(width, 40))
        self.collapse_btn.setIcon(glyph_icon("menu", "MUTED"))
        tip = "Show menu names (Ctrl+B)" if narrow else "Hide menu names (Ctrl+B)"
        self.collapse_btn.setToolTip(tip)
        self.collapse_btn.setAccessibleName(tip)
        key = style.theme() if style.theme() in THEME_ORDER else "auto"
        nxt = THEME_ORDER[(THEME_ORDER.index(key) + 1) % len(THEME_ORDER)]
        self.theme_btn.setIcon(glyph_icon(key, "MUTED"))
        self.theme_btn.setText("" if narrow else f"Theme: {THEME_NAMES[key]}")
        tip = f"Theme: {THEME_NAMES[key]}. Click for {THEME_NAMES[nxt]} (Ctrl+Shift+T)"
        self.theme_btn.setToolTip(tip)
        self.theme_btn.setAccessibleName(tip)

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
        if info is None:
            return
        self.library.show_update(info, lambda: self.update_now(info), updater.action_label(info))
        self.statusBar().showMessage(f"Gleaner {info.version} is available.", 15000)
        # Tell the user right away, without blocking the window.
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Update available")
        box.setText(f"Gleaner {info.version} is available. You have {__version__}.")
        notes = "\n".join(line.lstrip("#").strip() for line in (info.notes or "").splitlines() if line.strip())
        box.setInformativeText((notes[:400] + ("..." if len(notes) > 400 else "") + "\n\n" if notes else "")
                               + "Your recipes, collected data and Excel files are kept.")
        update_btn = box.addButton(updater.action_label(info), QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(update_btn)
        box.buttonClicked.connect(lambda clicked: clicked is update_btn and self.update_now(info))
        box.open()
        self.update_box = box

    @property
    def updater(self):
        if self._updater is None:
            self._updater = updater.Updater(self, self._ready_to_update, self._quit_for_update)
        return self._updater

    def update_now(self, info):
        self.updater.update(info)

    def _ready_to_update(self) -> bool:
        if self.run_view.running:
            QMessageBox.information(self, "A run is in progress",
                                    "Gleaner is collecting. Stop the run (or let it finish), then click Update now "
                                    "again. The new installer is already downloaded.")
            return False
        return self.builder.confirm_discard()

    def _quit_for_update(self):
        self._updating = True  # the checks are done; don't ask again on close
        self.close()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self._updating:
            event.accept()
            return
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
