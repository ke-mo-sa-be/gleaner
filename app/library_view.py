"""Library: list, run, edit, duplicate, export, import and delete recipes (PRD Feature 4)."""

import sqlite3
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QMessageBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app import settings, style
from app.tasks import friendly_error, run_task, with_store
from app.widgets import Banner, button, label, open_path
from core.export import export_workbook
from core.recipe import RecipeError, load_recipe

STATUS_LABELS = {  # status -> (text, colour key in app.style)
    None: ("Never run", "MUTED"),
    "running": ("Running", "WARNING"),
    "done": ("Done", "SUCCESS"),
    "stopped": ("Stopped", "WARNING"),
    "interrupted": ("Interrupted", "WARNING"),
    "blocked": ("BLOCKED", "ERROR"),
    "disallowed": ("Not allowed", "ERROR"),
    "network_error": ("Network problem", "WARNING"),
    "no_items": ("No items found", "WARNING"),
}


def _export(store, recipe_id, folder):
    return export_workbook(folder, store.get_recipe(recipe_id), store.records(recipe_id), store.runs(recipe_id))


class LibraryView(QWidget):
    edit_requested = Signal(object)  # recipe id, or None for a new recipe
    run_requested = Signal(int)
    help_requested = Signal(str)  # guide section key

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.setObjectName("view")
        self.store = store
        self.rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(label("Recipes", "h1"))
        layout.addWidget(label("A recipe tells Gleaner what to collect from one website. "
                               "Make one once, then run it any time.", "hint", wrap=True))

        bar = QHBoxLayout()
        self.new_btn = button("New recipe", "primary")
        self.run_btn = button("Run")
        self.edit_btn = button("Edit")
        self.dup_btn = button("Duplicate")
        self.export_btn = button("Export to Excel")
        self.import_btn = button("Import file...")
        self.delete_btn = button("Delete", "danger")
        for b in (self.new_btn, self.run_btn, self.edit_btn, self.dup_btn, self.export_btn, self.import_btn):
            bar.addWidget(b)
        bar.addStretch(1)
        bar.addWidget(self.delete_btn)
        layout.addLayout(bar)

        self.banner = Banner()
        layout.addWidget(self.banner)
        self.guide_banner = Banner()
        layout.addWidget(self.guide_banner)
        if not settings.guide_seen():
            self.guide_banner.show_message(
                "info", "New to Gleaner? The 5-minute guide walks you through your first recipe.", "",
                [("Open the guide", self._open_guide), ("Hide", self._hide_guide)])

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Website", "Records", "Last run", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(lambda _i: self._edit())
        self.table.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self.table, 1)
        self.empty = label("No recipes yet. Click New recipe, open a website and click on what you want "
                           "to collect.", "hint", wrap=True)
        layout.addWidget(self.empty)

        self.new_btn.clicked.connect(lambda: self.edit_requested.emit(None))
        self.edit_btn.clicked.connect(self._edit)
        self.run_btn.clicked.connect(self._run)
        self.dup_btn.clicked.connect(self._duplicate)
        self.export_btn.clicked.connect(self._export)
        self.import_btn.clicked.connect(self._import)
        self.delete_btn.clicked.connect(self._delete)
        style.theme_changed.changed.connect(self.refresh)
        self.refresh()

    def _open_guide(self):
        self._hide_guide()
        self.help_requested.emit("start")

    def _hide_guide(self):
        settings.set_guide_seen(True)
        self.guide_banner.hide()

    def show_update(self, info, on_download):
        self.banner.show_message("info", f"Gleaner {info.version} is available (you have an older version).",
                                 info.notes[:300] if info.notes else "",
                                 [("Download", on_download), ("Later", self.banner.hide)])

    def refresh(self):
        selected = self.selected_id()
        self.rows = self.store.list_recipes()
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            status_text, colour_key = STATUS_LABELS.get(row["last_status"], (row["last_status"], "MUTED"))
            values = [row["name"], urlsplit(row["start_url"]).hostname or "", f"{row['record_count']:,}",
                      (row["last_run_at"] or "").replace("T", " ")[:16], status_text]
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                if c == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 4:
                    item.setForeground(QColor(style.color(colour_key)))
                self.table.setItem(r, c, item)
            if row["id"] == selected:
                self.table.selectRow(r)
        self.empty.setVisible(not self.rows)
        self._update_buttons()

    def selected_id(self):
        r = self.table.currentRow()
        if not self.table.selectedItems() or r < 0 or r >= len(self.rows):
            return None
        return self.rows[r]["id"]

    def _update_buttons(self):
        has = self.selected_id() is not None
        for b in (self.run_btn, self.edit_btn, self.dup_btn, self.export_btn, self.delete_btn):
            b.setEnabled(has)

    def _edit(self):
        if self.selected_id() is not None:
            self.edit_requested.emit(self.selected_id())

    def _run(self):
        if self.selected_id() is not None:
            self.run_requested.emit(self.selected_id())

    def _duplicate(self):
        recipe_id = self.selected_id()
        recipe = self.store.get_recipe(recipe_id)
        base, n = recipe.name, 2
        recipe.name = f"{base} (copy)"
        while self.store.find_recipe(recipe.name) is not None:
            recipe.name = f"{base} (copy {n})"
            n += 1
        self.store.save_recipe(recipe)
        self.refresh()

    def _export(self):
        recipe_id = self.selected_id()
        self.banner.show_message("info", "Writing Excel file...")
        run_task(with_store(_export), recipe_id, settings.exports_dir(), on_done=self._exported,
                 on_failed=lambda msg: self.banner.show_message("error", "Couldn't write the Excel file.", msg))

    def _exported(self, result):
        path, ready, review = result
        self.banner.show_message("success", f"Excel written: {ready:,} ready, {review:,} need review.", str(path),
                                 [("Open Excel", lambda: open_path(path)),
                                  ("Open folder", lambda: open_path(path.parent))])

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import recipe", "", "Recipe files (*.json)")
        if not path:
            return
        try:
            recipe = load_recipe(path)
            existing = self.store.find_recipe(recipe.name)
            if existing is not None:
                answer = QMessageBox.question(self, "Replace recipe?",
                                              f"A recipe called '{recipe.name}' already exists. Replace it?")
                if answer != QMessageBox.StandardButton.Yes:
                    return
            self.store.save_recipe(recipe, existing)
        except (RecipeError, OSError, sqlite3.Error) as exc:
            self.banner.show_message("error", "Couldn't import that file.", friendly_error(exc))
            return
        self.banner.show_message("success", f"Imported '{recipe.name}'.")
        self.refresh()

    def _delete(self):
        recipe_id = self.selected_id()
        row = next(r for r in self.rows if r["id"] == recipe_id)
        answer = QMessageBox.question(
            self, "Delete recipe?",
            f"Delete '{row['name']}' and its {row['record_count']:,} collected records?\n\n"
            "Excel files you already exported are kept.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.store.delete_recipe(recipe_id)
            self.refresh()
