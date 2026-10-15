"""Settings: appearance, default speed, where files go, updates, tutorial, about."""

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QLineEdit, QRadioButton, QScrollArea, QVBoxLayout, QWidget)

from app import __version__, settings, style
from app.tasks import run_task
from app.widgets import Banner, button, label, open_path
from core import paths, updates


def open_update(info):
    """Open the installer: a download link in the browser, or the file in a shared folder."""
    if info.url.lower().startswith("https://"):
        QDesktopServices.openUrl(QUrl(info.url))
    else:
        open_path(info.url)


def _section(layout, title, hint=None):
    layout.addSpacing(12)
    layout.addWidget(label(title, "h2"))
    if hint:
        layout.addWidget(label(hint, "hint", wrap=True))


class SettingsView(QWidget):
    help_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("view")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("view")
        scroll.setWidget(body)
        outer.addWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(label("Settings", "h1"))

        _section(layout, "Appearance")
        row = QHBoxLayout()
        row.addWidget(label("Theme"))
        self.theme = QComboBox()
        for key, text in settings.THEMES:
            self.theme.addItem(text, key)
        self.theme.setCurrentIndex(self.theme.findData(settings.theme()))
        self.theme.setAccessibleName("Theme")
        self.theme.currentIndexChanged.connect(self._theme_changed)
        style.theme_changed.changed.connect(self._sync_theme)  # the sidebar's theme button changes it too
        row.addWidget(self.theme)
        row.addStretch(1)
        layout.addLayout(row)

        _section(layout, "Collection speed",
                 "How long Gleaner waits between pages. This is the default for new runs; you can change it for "
                 "one run on the Run screen.")
        self.speed_group = QButtonGroup(self)
        for key, text, desc in settings.SPEED_CHOICES:
            radio = QRadioButton(text)
            radio.setChecked(key == settings.speed())
            radio.setProperty("speed", key)
            self.speed_group.addButton(radio)
            layout.addWidget(radio)
            hint = label(desc, "hint", wrap=True)
            hint.setContentsMargins(26, 0, 0, 4)
            layout.addWidget(hint)
        self.speed_group.buttonToggled.connect(self._speed_changed)

        _section(layout, "Where your files are")
        row = QHBoxLayout()
        row.addWidget(label("Excel files"))
        self.exports = QLineEdit(str(settings.exports_dir()))
        self.exports.setReadOnly(True)
        row.addWidget(self.exports, 1)
        change = button("Change...")
        change.clicked.connect(self._choose_exports)
        row.addWidget(change)
        open_exports = button("Open")
        open_exports.clicked.connect(lambda: self._open_folder(settings.exports_dir()))
        row.addWidget(open_exports)
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(label("Recipes, collected data and logs"))
        data = QLineEdit(str(paths.data_home()))
        data.setReadOnly(True)
        row.addWidget(data, 1)
        open_data = button("Open")
        open_data.clicked.connect(lambda: self._open_folder(paths.data_home()))
        row.addWidget(open_data)
        layout.addLayout(row)
        layout.addWidget(label("Collected data can include people's names and phone numbers. Keep these folders "
                               "on this PC, not on shared drives.", "hint", wrap=True))

        _section(layout, "Updates", f"You have Gleaner {__version__}.")
        self.auto_check = QCheckBox("Check for a new version when Gleaner starts")
        self.auto_check.setChecked(settings.auto_update_check())
        self.auto_check.toggled.connect(settings.set_auto_update_check)
        layout.addWidget(self.auto_check)
        row = QHBoxLayout()
        row.addWidget(label("Update source"))
        self.source = QLineEdit(settings.update_source() or updates.DEFAULT_SOURCE)
        self.source.setToolTip("github:owner/repo, or the path to latest.json in a shared folder")
        self.source.editingFinished.connect(lambda: settings.set_update_source(self.source.text()))
        row.addWidget(self.source, 1)
        self.check_btn = button("Check now")
        self.check_btn.clicked.connect(self._check_now)
        row.addWidget(self.check_btn)
        layout.addLayout(row)
        self.update_banner = Banner()
        layout.addWidget(self.update_banner)

        _section(layout, "Help")
        row = QHBoxLayout()
        guide = button("Open the guide")
        guide.clicked.connect(lambda: self.help_requested.emit("start"))
        row.addWidget(guide)
        reset = button("Show the welcome tip again")
        reset.clicked.connect(lambda: settings.set_guide_seen(False))
        row.addWidget(reset)
        row.addStretch(1)
        layout.addLayout(row)

        _section(layout, "About")
        layout.addWidget(label(f"Gleaner {__version__}. Collects public directory listings politely: one page at "
                               "a time, robots rules respected, stops the moment a site objects.", "hint", wrap=True))
        layout.addStretch(1)

    def _sync_theme(self):
        index = self.theme.findData(style.theme())
        if index >= 0 and index != self.theme.currentIndex():
            self.theme.blockSignals(True)
            self.theme.setCurrentIndex(index)
            self.theme.blockSignals(False)

    def _theme_changed(self, _index):
        key = self.theme.currentData()
        settings.set_theme(key)
        style.apply(QApplication.instance(), key)

    def _speed_changed(self, radio, checked):
        if checked:
            settings.set_speed(radio.property("speed"))

    def _choose_exports(self):
        folder = QFileDialog.getExistingDirectory(self, "Where should Excel files go?", str(settings.exports_dir()))
        if folder:
            settings.set_exports_dir(folder)
            self.exports.setText(folder)

    @staticmethod
    def _open_folder(path):
        path.mkdir(parents=True, exist_ok=True)
        open_path(path)

    def _check_now(self):
        settings.set_update_source(self.source.text())
        self.check_btn.setEnabled(False)
        self.update_banner.show_message("info", "Checking for a new version...")
        run_task(updates.check, self.source.text(), __version__, on_done=self._checked, on_failed=self._failed)

    def _checked(self, info):
        self.check_btn.setEnabled(True)
        if info is None:
            self.update_banner.show_message("success", f"You have the latest version ({__version__}).")
        else:
            self.update_banner.show_message(
                "info", f"Gleaner {info.version} is available.",
                (info.notes[:400] + "\n\n" if info.notes else "") +
                "Download it, close Gleaner, then run the installer. Your recipes and data are kept.",
                [("Download", lambda: open_update(info))])

    def _failed(self, message):
        self.check_btn.setEnabled(True)
        self.update_banner.show_message("warning", "Couldn't check for updates.", message)
