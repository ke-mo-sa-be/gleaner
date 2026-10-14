"""Look and feel from docs/DESIGN_SYSTEM.md: light and dark palettes, theme switching (auto follows Windows)."""

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
QMainWindow, QWidget#view, QStackedWidget {{ background: {BACKGROUND}; }}
QLabel[role="h1"] {{ font-size: 16pt; font-weight: 600; }}
QLabel[role="h2"] {{ font-size: 12pt; font-weight: 600; }}
QLabel[role="hint"] {{ color: {MUTED}; font-size: 9pt; }}
QLabel[role="instruction"] {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; padding: 8px; }}
QLabel[role="instruction"][state="error"] {{ border-color: {ERROR}; color: {ERROR}; }}
QLabel[role="steps"] {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 8px; }}
QLineEdit, QSpinBox, QComboBox {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 3px; padding: 4px 6px; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 2px solid {SECONDARY}; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; selection-background-color: {SELECTED}; selection-color: {TEXT}; }}
QPushButton {{ background: {SURFACE}; color: {PRIMARY}; border: 1px solid {PRIMARY}; border-radius: 4px; padding: 5px 12px; }}
QPushButton:hover {{ background: {SELECTED}; }}
QPushButton:disabled {{ color: {DISABLED_TEXT}; border-color: {BORDER}; background: {BACKGROUND}; }}
QPushButton[kind="primary"] {{ background: {PRIMARY}; color: {ON_PRIMARY}; }}
QPushButton[kind="primary"]:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton[kind="danger"] {{ background: {ERROR}; color: {ON_PRIMARY}; border-color: {ERROR}; }}
QPushButton[kind="primary"]:disabled, QPushButton[kind="danger"]:disabled {{ background: {DISABLED_FILL}; color: {SURFACE}; border-color: {DISABLED_FILL}; }}
QRadioButton {{ spacing: 8px; }}
QTableWidget {{ background: {SURFACE}; border: 1px solid {BORDER}; gridline-color: {BORDER}; }}
QHeaderView::section {{ background: {BACKGROUND}; color: {TEXT}; border: none; border-bottom: 1px solid {BORDER}; padding: 4px; font-weight: 600; }}
QListWidget#nav {{ background: {SURFACE}; border: none; border-right: 1px solid {BORDER}; padding-top: 8px; }}
QListWidget#nav::item {{ padding-left: 16px; }}
QListWidget#nav::item:selected {{ background: {SELECTED}; color: {PRIMARY}; font-weight: 600; }}
QListWidget#sections {{ background: {SURFACE}; border: 1px solid {BORDER}; }}
QListWidget#sections::item {{ padding-left: 8px; }}
QListWidget#sections::item:selected {{ background: {SELECTED}; color: {PRIMARY}; }}
QFrame#banner {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; }}
QPlainTextEdit, QTextBrowser {{ background: {SURFACE}; border: 1px solid {BORDER}; }}
QStatusBar {{ background: {BACKGROUND}; color: {MUTED}; }}
"""

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
    app.setFont(QFont("Segoe UI", 10))
    app.setPalette(_palette(_current))
    app.setStyleSheet(STYLESHEET.format(**_current))
    if not _hooked:
        hints.colorSchemeChanged.connect(lambda _scheme: _follow_system(app))
        _hooked = True
    theme_changed.changed.emit()


def _follow_system(app):
    if _theme == "auto" and is_dark() != _system_is_dark(app):
        apply(app, "auto")
