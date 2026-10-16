"""Small shared widgets."""

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout

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


# Windows' own icon fonts (Windows 11 / Windows 10). Code points from Segoe MDL2 Assets, also in Fluent Icons.
ICON_FONTS = ["Segoe Fluent Icons", "Segoe MDL2 Assets"]
GLYPHS = {"menu": "", "library": "", "builder": "", "run": "", "guide": "",
          "settings": "", "auto": "", "light": "", "dark": "", "back": "",
          "forward": "", "reload": "", "link": ""}


def glyph_icon(name, color_key="TEXT", size=20) -> QIcon:
    """An icon drawn from the Windows icon font in the current theme's colour."""
    pixmap = QPixmap(size * 2, size * 2)  # drawn at 2x so it stays sharp on high-DPI screens
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(2)
    painter = QPainter(pixmap)
    font = QFont()
    font.setFamilies(ICON_FONTS)
    font.setPixelSize(int(size * 0.8))
    painter.setFont(font)
    painter.setPen(QColor(style.color(color_key)))
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, GLYPHS[name])
    painter.end()
    return QIcon(pixmap)


def icon_button(glyph, tooltip):
    """A small borderless button showing one icon, e.g. the builder's back and forward buttons."""
    b = QToolButton()
    b.setObjectName("iconButton")
    b.setProperty("glyph", glyph)
    b.setIcon(glyph_icon(glyph, "MUTED"))
    b.setIconSize(QSize(18, 18))
    b.setToolTip(tooltip)
    b.setAccessibleName(tooltip.split(" (")[0])
    return b


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
