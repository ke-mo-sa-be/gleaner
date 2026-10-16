"""Look and feel from docs/DESIGN_SYSTEM.md: light and dark palettes, theme switching (auto follows Windows)."""

from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette

LIGHT = {
    "PRIMARY": "#1F4E78", "PRIMARY_HOVER": "#173D5E", "ON_PRIMARY": "#FFFFFF", "SECONDARY": "#2E86C1",
    "BACKGROUND": "#F7F8FA", "SURFACE": "#FFFFFF", "TEXT": "#1B1F24", "MUTED": "#5F6B7A", "BORDER": "#D6DBE1",
    "SELECTED": "#EAF2F8", "DISABLED_TEXT": "#9AA5B1", "DISABLED_FILL": "#C5CDD6",
    "SUCCESS": "#1E8449", "WARNING": "#B9770E", "ERROR": "#C0392B",
}
DARK = {
    "PRIMARY": "#5DA9E9", "PRIMARY_HOVER": "#7BBAEE", "ON_PRIMARY": "#0F1418", "SECONDARY": "#5DADE2",
    "BACKGROUND": "#15191E", "SURFACE": "#1E242B", "TEXT": "#E6EAEF", "MUTED": "#9AA5B1", "BORDER": "#323C47",
    "SELECTED": "#23384A", "DISABLED_TEXT": "#5F6B7A", "DISABLED_FILL": "#323C47",
    "SUCCESS": "#3FBF7F", "WARNING": "#E0A63A", "ERROR": "#E5675A",
}

STYLESHEET = """
QWidget {{ color: {TEXT}; }}
QMainWindow, QWidget#view, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BACKGROUND}; }}
QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 8px; }}
QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#card QStackedWidget {{ background: transparent; }}
QFrame#card QLineEdit, QFrame#card QComboBox, QFrame#card QTableWidget, QFrame#card QListWidget {{ background: {SURFACE}; }}
QLabel[role="h1"] {{ font-size: 18pt; font-weight: 600; }}
QLabel[role="h2"] {{ font-size: 10.5pt; font-weight: 600; }}
QLabel[role="hint"] {{ color: {MUTED}; font-size: 9pt; }}
QLabel[role="instruction"] {{ background: {SELECTED}; border: none; border-left: 3px solid {PRIMARY}; border-radius: 6px; padding: 8px 10px; }}
QLabel[role="instruction"][state="error"] {{ border-left-color: {ERROR}; color: {ERROR}; }}
QLabel[role="steps"] {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 8px; }}
QLineEdit, QSpinBox, QComboBox {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; padding: 5px 8px; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {SECONDARY}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url({ICONS}/chevron-down.svg); width: 10px; height: 6px; }}
QSpinBox {{ padding: 4px 22px 4px 8px; }}
QSpinBox::up-button, QSpinBox::down-button {{ subcontrol-origin: border; width: 20px; border: none; border-left: 1px solid {BORDER}; background: transparent; }}
QSpinBox::up-button {{ subcontrol-position: top right; border-top-right-radius: 6px; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; border-bottom-right-radius: 6px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {SELECTED}; }}
QSpinBox::up-arrow {{ image: url({ICONS}/chevron-up.svg); width: 10px; height: 6px; }}
QSpinBox::down-arrow {{ image: url({ICONS}/chevron-down.svg); width: 10px; height: 6px; }}
QProgressBar {{ background: {BORDER}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 3px; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; border: 1px solid {BORDER}; selection-background-color: {SELECTED}; selection-color: {TEXT}; outline: none; }}
QFrame#card QLineEdit#title {{ background: transparent; border: none; border-bottom: 1px solid {BORDER}; border-radius: 0; font-size: 13pt; font-weight: 600; padding: 2px 0 4px 0; }}
QFrame#card QLineEdit#title:focus {{ border-bottom: 2px solid {SECONDARY}; }}
QFrame#card QLineEdit#address {{ background: {BACKGROUND}; border: 1px solid transparent; border-radius: 15px; padding: 5px 14px; }}
QFrame#card QLineEdit#address:focus {{ border: 1px solid {SECONDARY}; }}
QComboBox#cell {{ border: none; background: transparent; padding: 2px 4px; }}
QPushButton {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {PRIMARY}; color: {PRIMARY}; }}
QPushButton:pressed {{ background: {SELECTED}; }}
QPushButton:disabled {{ color: {DISABLED_TEXT}; border-color: {BORDER}; background: transparent; }}
QPushButton[kind="primary"] {{ background: {PRIMARY}; color: {ON_PRIMARY}; border-color: {PRIMARY}; font-weight: 600; }}
QPushButton[kind="primary"]:hover {{ background: {PRIMARY_HOVER}; border-color: {PRIMARY_HOVER}; color: {ON_PRIMARY}; }}
QPushButton[kind="danger"] {{ background: {ERROR}; color: {ON_PRIMARY}; border-color: {ERROR}; }}
QPushButton[kind="danger"]:hover {{ color: {ON_PRIMARY}; }}
QPushButton[kind="primary"]:disabled, QPushButton[kind="danger"]:disabled {{ background: {DISABLED_FILL}; color: {SURFACE}; border-color: {DISABLED_FILL}; }}
QPushButton[kind="quiet"] {{ background: transparent; border: none; color: {MUTED}; padding: 5px 8px; }}
QPushButton[kind="quiet"]:hover {{ background: {SELECTED}; color: {TEXT}; }}
QPushButton[kind="quiet"]:disabled {{ color: {DISABLED_TEXT}; }}
QPushButton[kind="link"] {{ background: transparent; border: none; color: {PRIMARY}; padding: 5px 0; }}
QPushButton[kind="link"]:hover {{ text-decoration: underline; }}
QToolButton#iconButton {{ background: transparent; border: none; border-radius: 6px; padding: 5px; }}
QToolButton#iconButton:hover {{ background: {SELECTED}; }}
QToolButton#more {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 14px; }}
QToolButton#more:hover {{ border-color: {PRIMARY}; color: {PRIMARY}; }}
QToolButton#more:disabled {{ color: {DISABLED_TEXT}; }}
QToolButton#more::menu-indicator {{ image: none; width: 0; }}
QMenu {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: {SELECTED}; color: {TEXT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}
QToolButton#disclosure {{ background: transparent; border: none; font-weight: 600; padding: 2px 0; }}
QTabBar#steps::tab {{ background: transparent; border: none; border-bottom: 2px solid {BORDER}; color: {MUTED}; font-weight: 600; padding: 8px 6px; }}
QTabBar#steps::tab:selected {{ color: {PRIMARY}; border-bottom: 2px solid {PRIMARY}; }}
QTabBar#steps::tab:hover:!selected {{ color: {TEXT}; }}
QRadioButton {{ spacing: 8px; }}
QTableWidget {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; gridline-color: {BORDER}; alternate-background-color: {BACKGROUND}; selection-background-color: {SELECTED}; selection-color: {TEXT}; outline: none; }}
QTableWidget#plain {{ border: none; border-radius: 0; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: {SURFACE}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER}; padding: 6px 6px; font-weight: 600; }}
QListWidget#nav {{ background: {SURFACE}; border: none; padding-top: 4px; outline: none; }}
QListWidget#nav::item {{ padding-left: 14px; border-radius: 6px; margin: 1px 6px; }}
QListWidget#nav::item:hover:!selected {{ background: {BACKGROUND}; }}
QWidget#sidebar {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
QToolButton#navButton {{ background: transparent; border: none; color: {MUTED}; padding: 10px 14px; text-align: left; }}
QToolButton#navButton:hover {{ background: {SELECTED}; color: {TEXT}; }}
QListWidget#nav::item:selected {{ background: {SELECTED}; color: {PRIMARY}; font-weight: 600; }}
QListWidget#sections, QListWidget#plain {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; outline: none; }}
QListWidget#sections::item {{ padding-left: 8px; }}
QListWidget#sections::item:selected, QListWidget#plain::item:selected {{ background: {SELECTED}; color: {PRIMARY}; }}
QFrame#banner {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
QPlainTextEdit, QTextBrowser {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; }}
QStatusBar {{ background: {BACKGROUND}; color: {MUTED}; }}
QSplitter::handle {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 3px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background: {MUTED}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ width: 0; height: 0; background: none; }}
"""

ICONS = (Path(__file__).with_name("icons")).as_posix()  # chevrons for combo and spin boxes

BANNER_KEYS = {"success": "SUCCESS", "warning": "WARNING", "error": "ERROR", "info": "SECONDARY"}

_current = LIGHT
_theme = "auto"
_hooked = False


class _Notifier(QObject):
    changed = Signal()


theme_changed = _Notifier()  # connect to .changed to recolour widgets that paint their own colours


def color(key: str) -> str:
    return _current[key]


def is_dark() -> bool:
    return _current is DARK


def theme() -> str:
    """The chosen theme: "auto", "light" or "dark"."""
    return _theme


def _palette(p) -> QPalette:
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: p["BACKGROUND"], QPalette.ColorRole.WindowText: p["TEXT"],
        QPalette.ColorRole.Base: p["SURFACE"], QPalette.ColorRole.AlternateBase: p["BACKGROUND"],
        QPalette.ColorRole.Text: p["TEXT"], QPalette.ColorRole.Button: p["SURFACE"],
        QPalette.ColorRole.ButtonText: p["TEXT"], QPalette.ColorRole.Highlight: p["SECONDARY"],
        QPalette.ColorRole.HighlightedText: "#FFFFFF", QPalette.ColorRole.ToolTipBase: p["SURFACE"],
        QPalette.ColorRole.ToolTipText: p["TEXT"], QPalette.ColorRole.PlaceholderText: p["MUTED"],
        QPalette.ColorRole.Link: p["PRIMARY"],
    }
    for role, value in roles.items():
        pal.setColor(role, QColor(value))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(p["DISABLED_TEXT"]))
    return pal


def _system_is_dark(app) -> bool:
    return app.styleHints().colorScheme() == Qt.ColorScheme.Dark


def apply(app, theme: str = "auto"):
    """theme: "auto" (follow Windows), "light" or "dark"."""
    global _current, _theme, _hooked
    _theme = theme
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):  # Qt 6.8+: also switches the Windows title bar
        scheme = {"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}.get(theme, Qt.ColorScheme.Unknown)
        hints.setColorScheme(scheme)
    dark = theme == "dark" or (theme == "auto" and _system_is_dark(app))
    _current = DARK if dark else LIGHT
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI"])  # Windows 11's UI font, Windows 10's otherwise
    font.setPointSize(10)
    app.setFont(font)
    app.setPalette(_palette(_current))
    app.setStyleSheet(STYLESHEET.format(ICONS=ICONS, **_current))
    if not _hooked:
        hints.colorSchemeChanged.connect(lambda _scheme: _follow_system(app))
        _hooked = True
    theme_changed.changed.emit()


def _follow_system(app):
    if _theme == "auto" and is_dark() != _system_is_dark(app):
        apply(app, "auto")
