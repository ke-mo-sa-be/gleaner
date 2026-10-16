"""Library: list, run, edit, duplicate, export, import and delete recipes (PRD Feature 4)."""

import sqlite3
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
                               QHeaderView, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                               QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget)

from app import settings, style
from app.tasks import friendly_error, run_task, with_store
from app.widgets import Banner, button, label, open_path
from core.export import export_workbook, safe_stem
from core.master import export_master
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


def _master(store, recipe_ids, folder):
    sources = [(store.get_recipe(i), store.records(i), store.last_run(i)) for i in recipe_ids]
    return export_master(folder, sources)


class MasterDialog(QDialog):
    """Pick the recipes to combine into one master list."""

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Master list")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.addWidget(label("Combine these recipes into one Excel file. The same phone number (or email) found "
                               "in several recipes is kept once; the others go to Needs Review.", wrap=True))
        self.list = QListWidget()
        for row in rows:
            item = QListWidgetItem(f"{row['name']}  ({row['record_count']:,} records)")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if row["record_count"] else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create Excel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_ids(self):
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked]


class PersonDialog(QDialog):
    """Find & delete person: remove someone's records everywhere and never collect them again (DPDP)."""

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.found = []
        self.deleted = 0
        self.setWindowTitle("Find & delete person")
        self.setMinimumSize(640, 420)
        layout = QVBoxLayout(self)
        layout.addWidget(label("When someone asks to be removed, search for their phone number, email or name. "
                               "Tick their records and delete them. Gleaner then won't collect them again.",
                               wrap=True))
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Phone number, email or name")
        self.query.setAccessibleName("Search for a person")
        self.query.returnPressed.connect(self.search)
        row.addWidget(self.query, 1)
        self.search_btn = button("Search", "primary")
        self.search_btn.clicked.connect(self.search)
        row.addWidget(self.search_btn)
        layout.addLayout(row)
        self.result_label = label("", "hint", wrap=True)
        layout.addWidget(self.result_label)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Delete", "Recipe", "Record"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)
        layout.addWidget(label("Excel files you already exported still contain these records. Delete or edit "
                               "those files by hand.", "hint", wrap=True))
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.delete_btn = button("Delete and don't collect again", "danger")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self.delete_ticked)
        close = button("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(self.delete_btn)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def search(self):
        text = self.query.text().strip()
        if len(text) < 3:
            self.result_label.setText("Type at least 3 characters.")
            return
        self.found = self.store.find_person(text)
        self.table.setRowCount(len(self.found))
        for r, rec in enumerate(self.found):
            tick = QTableWidgetItem()
            tick.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            tick.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(r, 0, tick)
            self.table.setItem(r, 1, QTableWidgetItem(rec["recipe"]))
            summary = " | ".join(str(v) for k, v in rec["data"].items() if v and not k.startswith("_"))
            self.table.setItem(r, 2, QTableWidgetItem(summary[:200]))  # plain text only
        self.table.resizeColumnsToContents()
        self.result_label.setText(f"{len(self.found)} matching records." if self.found else
                                  "No collected records match. Nothing to delete.")
        self.delete_btn.setEnabled(bool(self.found))

    def ticked_ids(self):
        return [rec["id"] for r, rec in enumerate(self.found)
                if self.table.item(r, 0).checkState() == Qt.CheckState.Checked]

    def delete_ticked(self):
        ids = self.ticked_ids()
        if not ids:
            self.result_label.setText("Tick the records to delete.")
            return
        answer = QMessageBox.question(
            self, "Delete records?",
            f"Delete {len(ids)} records for good and add this person to the do-not-collect list?\n\n"
            "This can't be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.deleted += self.store.delete_people(ids)
        self.table.setRowCount(0)
        self.found = []
        self.delete_btn.setEnabled(False)
        self.result_label.setText(f"Deleted {len(ids)} records. Gleaner won't collect them again.")


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
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(12)

        # Header: title on the left, actions for the whole library on the right.
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("Recipes", "h1"))
        titles.addWidget(label("A recipe tells Gleaner what to collect from one website. "
                               "Make one once, then run it any time.", "hint", wrap=True))
        head.addLayout(titles, 1)
        self.person_btn = button("Find && delete person...", "quiet",  # && shows one "&" (one alone underlines)
                                 tooltip="Remove someone who asked not to be listed, and never collect them again")
        self.person_btn.setAccessibleName("Find & delete person...")
        self.import_btn = button("Import recipe...", "quiet")
        self.master_btn = button("Master list...", tooltip="All recipes in one Excel file, duplicates removed")
        self.new_btn = button("New recipe", "primary")
        for b in (self.person_btn, self.import_btn, self.master_btn, self.new_btn):
            head.addWidget(b, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(head)

        # Actions for the selected recipe; the rarer ones sit in the More menu.
        bar = QHBoxLayout()
        self.run_btn = button("Run", "primary")
        self.edit_btn = button("Edit")
        self.export_btn = button("Export to Excel")
        self.more_btn = QToolButton()
        self.more_btn.setObjectName("more")
        self.more_btn.setText("More  ▾")
        self.more_btn.setToolTip("Duplicate, share or delete the selected recipe")
        self.more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.more_btn)
        self.dup_btn = menu.addAction("Duplicate")
        self.share_btn = menu.addAction("Share recipe...")
        self.share_btn.setToolTip("Save this recipe as a file a colleague can import")
        menu.addSeparator()
        self.delete_btn = menu.addAction("Delete...")
        self.more_btn.setMenu(menu)
        self.selected_label = label("", "hint")
        for b in (self.run_btn, self.edit_btn, self.export_btn, self.more_btn):
            bar.addWidget(b)
        bar.addSpacing(8)
        bar.addWidget(self.selected_label)
        bar.addStretch(1)
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
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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
        self.dup_btn.triggered.connect(self._duplicate)
        self.export_btn.clicked.connect(self._export)
        self.import_btn.clicked.connect(self._import)
        self.share_btn.triggered.connect(self._share)
        self.master_btn.clicked.connect(self._choose_master)
        self.delete_btn.triggered.connect(self._delete)
        self.person_btn.clicked.connect(self._find_person)
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
        self.master_btn.setEnabled(bool(self.rows))
        for b in (self.run_btn, self.edit_btn, self.dup_btn, self.export_btn, self.share_btn, self.delete_btn,
                  self.more_btn):
            b.setEnabled(has)
        row = next((r for r in self.rows if r["id"] == self.selected_id()), None)
        self.selected_label.setText(row["name"] if row else "Select a recipe to run, edit or export it.")

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

    def _choose_master(self):
        dialog = MasterDialog(self.rows, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.create_master(dialog.selected_ids())

    def create_master(self, recipe_ids):
        if not recipe_ids:
            self.banner.show_message("warning", "Tick at least one recipe for the master list.")
            return
        self.banner.show_message("info", "Writing the master list...")
        run_task(with_store(_master), recipe_ids, settings.exports_dir(), on_done=self._master_written,
                 on_failed=lambda msg: self.banner.show_message("error", "Couldn't write the master list.", msg))

    def _master_written(self, result):
        path, n_master, n_review = result
        self.banner.show_message("success", f"Master list written: {n_master:,} rows, {n_review:,} need review.",
                                 str(path), [("Open Excel", lambda: open_path(path)),
                                             ("Open folder", lambda: open_path(path.parent))])

    def _share(self):
        recipe = self.store.get_recipe(self.selected_id())
        path, _ = QFileDialog.getSaveFileName(self, "Share recipe", f"{safe_stem(recipe.name)}.json",
                                              "Recipe files (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(recipe.to_json())
        except OSError as exc:
            self.banner.show_message("error", "Couldn't save the recipe file.", str(exc))
            return
        self.banner.show_message("success", "Recipe saved. Send the file to a colleague; they click "
                                            "Import recipe... in their Library.", path)

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

    def _find_person(self):
        dialog = PersonDialog(self.store, self)
        dialog.exec()
        if dialog.deleted:
            self.refresh()
            self.banner.show_message("success", f"Deleted {dialog.deleted:,} records. They are on the "
                                                "do-not-collect list now.",
                                     "Excel files you exported earlier still contain them: delete or edit "
                                     "those files by hand.")

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
