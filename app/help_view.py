"""Help: the user guide (docs/USER_GUIDE.md), one chapter at a time with a contents list."""

import sys
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QTextBrowser, QVBoxLayout, QWidget

from app.widgets import label

# Section keys other screens can open, matched against the start of a chapter title.
KEYS = {
    "start": "Getting started",
    "pages": "The three kinds of page",
    "builder": "Tutorial",
    "layers": "Directories with many layers",
    "running": "Running a recipe",
    "speed": "Speed",
    "excel": "Your Excel file",
    "blocked": "When a site says no",
    "updates": "Updates",
}


def guide_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "docs" / "USER_GUIDE.md"


def load_chapters(path=None) -> list[tuple[str, str]]:
    """[(title, markdown body)] from the guide's '## ' headings."""
    try:
        text = (path or guide_path()).read_text(encoding="utf-8")
    except OSError:
        return [("Guide", "The guide could not be found. Reinstall Gleaner to restore it.")]
    chapters, title, lines = [], None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if title:
                chapters.append((title, "\n".join(lines).strip()))
            title, lines = line[3:].strip(), []
        elif title:
            lines.append(line)
    if title:
        chapters.append((title, "\n".join(lines).strip()))
    return chapters


class HelpView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("view")
        self.chapters = load_chapters()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(label("Guide", "h1"))
        layout.addWidget(label("Start with \"Tutorial: your first recipe\" if this is your first time.",
                               "hint", wrap=True))
        row = QHBoxLayout()
        self.contents = QListWidget()
        self.contents.setObjectName("sections")
        self.contents.setFixedWidth(260)
        self.contents.setAccessibleName("Chapters")
        for i, (title, _body) in enumerate(self.chapters, start=1):
            item = QListWidgetItem(f"{i}. {title}")
            item.setSizeHint(QSize(250, 30))
            self.contents.addItem(item)
        row.addWidget(self.contents)
        self.page = QTextBrowser()
        self.page.setOpenExternalLinks(False)
        self.page.setAccessibleName("Chapter text")
        row.addWidget(self.page, 1)
        layout.addLayout(row, 1)

        self.contents.currentRowChanged.connect(self._show)
        self.contents.setCurrentRow(0)

    def _show(self, row):
        if 0 <= row < len(self.chapters):
            title, body = self.chapters[row]
            self.page.setMarkdown(f"## {title}\n\n{body}")

    def show_section(self, key):
        prefix = KEYS.get(key, "")
        row = next((i for i, (title, _b) in enumerate(self.chapters) if title.startswith(prefix)), 0)
        self.contents.setCurrentRow(row)
