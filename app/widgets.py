"""Small shared widgets."""

import os
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app import style


def button(text, kind=None, tooltip=None):
    b = QPushButton(text)
    if kind:
        b.setProperty("kind", kind)
    b.setAccessibleName(text)
    if tooltip:
        b.setToolTip(tooltip)
    return b


def label(text="", role=None, wrap=False):
    lab = QLabel(text)
    if role:
        lab.setProperty("role", role)
    lab.setWordWrap(wrap)
    return lab


def restyle(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def open_path(path):
    """Open a file or folder with Windows' default program."""
    path = Path(path)
    if hasattr(os, "startfile"):
        os.startfile(path)  # noqa: S606 - local file the app wrote itself
    else:
        subprocess.Popen(["xdg-open", str(path)])


class Banner(QFrame):
    """Outcome message: coloured stripe, title, optional details, optional action buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("banner")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 12, 0)
        self.stripe = QFrame()
        self.stripe.setFixedWidth(4)
        outer.addWidget(self.stripe)
        body = QVBoxLayout()
        body.setContentsMargins(8, 10, 0, 10)
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-weight: 600;")
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setProperty("role", "hint")
        body.addWidget(self.title)
        body.addWidget(self.details)
        outer.addLayout(body, 1)
        self.actions = QHBoxLayout()
        outer.addLayout(self.actions)
        self.hide()

    def show_message(self, kind, title, details="", actions=()):
        self.stripe.setStyleSheet(f"background: {style.color(style.BANNER_KEYS[kind])}; border-radius: 2px;")
        self.title.setText(title)
        self.details.setText(details)
        self.details.setVisible(bool(details))
        while self.actions.count():
            w = self.actions.takeAt(0).widget()
            if w:
                w.deleteLater()
        for text, callback in actions:
            b = button(text)
            b.clicked.connect(callback)
            self.actions.addWidget(b)
        self.show()
