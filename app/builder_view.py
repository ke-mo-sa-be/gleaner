"""Recipe Builder: point and click on a website to teach Gleaner what to collect (UX Flows 1-3)."""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QInputDialog, QLineEdit,
                               QListWidget, QMessageBox, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from app.tasks import run_task, with_store
from app.web import PickerPage
from app.widgets import button, label, restyle
from core.extract import extract_detail, extract_list
from core.fetcher import Fetcher
from core.recipe import Detail, Field, Pagination, Recipe, RecipeError, check_url, validate

log = logging.getLogger(__name__)

FIELD_TYPES = [("Text", "text"), ("Link", "link"), ("Phone", "phone"), ("Email", "email"),
               ("Pincode", "pincode"), ("Number", "number")]
SENSITIVE = re.compile(r"birth|\bdob\b|aadha?ar|\bpan\b|bank|account\s*(no|number)|ifsc|card\s*(no|number)", re.I)
EMAIL_LIKE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PREVIEW_ROWS = 10

INSTRUCTIONS = {
    "idle": "Type the website address and click Open. Go to the page that lists the items you want "
            "(you can use the site's own filters first), then use the buttons below.",
    "list": "Click an example of a value you want, for example a name or a title. Every matching item lights "
            "up. Press Esc to cancel.",
    "link": "Click the link or button that opens one item's own page (for example 'View details').",
    "next": "Click the site's Next button, or the link to page 2.",
    "detail": "Click a value you want on this page, for example the phone number. Press Esc to cancel.",
}

FRIENDLY_PROBLEMS = {
    "name is empty": "Give the recipe a name.",
    "list.item_selector is empty": "Add at least one list field.",
    "list has no fields": "Add at least one list field.",
}


@dataclass
class BuilderField:
    page: str  # "list" or "detail"
    field: Field
    steps: list | None = None
    found: str = ""
    is_link: bool = False


def guess_type(sample):
    sample = (sample or "").strip()
    if EMAIL_LIKE.search(sample):
        return "email"
    digits = re.sub(r"\D", "", sample)
    if re.fullmatch(r"[1-9]\d{2}\s?\d{3}", sample):
        return "pincode"
    if len(digits) >= 10 and len(digits) >= 0.7 * len(re.sub(r"\s", "", sample)):
        return "phone"
    return "text"


# Tests only: e.g. {"min_delay": 0, "max_delay": 0, "_min_delay_floor": 0} against the local fixture site.
FETCHER_OPTIONS = {}


def _fetcher(store):
    return Fetcher(store, **FETCHER_OPTIONS)


def _robots_allows(store, url):
    return _fetcher(store).allowed(url)


def _raw_item_count(store, recipe):
    """Items found in the page as the server sends it (what a run sees), via one polite request."""
    html = _fetcher(store).get(recipe.start_url)
    return len(extract_list(html, recipe, recipe.start_url))


def _fetch_details(store, recipe, links):
    fetcher = _fetcher(store)
    return [extract_detail(fetcher.get(link), recipe, link) for link in links]


class BuilderView(QWidget):
    saved = Signal(int)
    help_requested = Signal(str)  # guide section key

    def __init__(self, store, parent=None, allow_local=False):
        super().__init__(parent)
        self.setObjectName("view")
        self.store = store
        self.allow_local = allow_local  # tests only (local fixture site)
        self._build_ui()
        self.page = PickerPage(parent=self)
        self.view.setPage(self.page)
        self.page.picked.connect(self._on_picked)
        self.page.loadStarted.connect(self._on_load_started)
        self.page.loadFinished.connect(self._on_loaded)
        self.page.urlChanged.connect(self._on_url_changed)
        self.new_recipe()

    # ---- layout ------------------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        top = QHBoxLayout()
        top.addWidget(label("Recipe name"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Shops - Pune - Electronics")
        top.addWidget(self.name_edit, 1)
        top.addWidget(label("  Website address"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("e.g. https://www.example.com/doctors")
        self.url_edit.returnPressed.connect(self.open_url)
        top.addWidget(self.url_edit, 3)
        self.open_btn = button("Open")
        self.open_btn.clicked.connect(self.open_url)
        top.addWidget(self.open_btn)
        root.addLayout(top)

        self.view = QWebEngineView()
        panel = QWidget()
        side = QVBoxLayout(panel)
        side.setContentsMargins(12, 0, 0, 0)
        self.instruction = label(INSTRUCTIONS["idle"], "instruction", wrap=True)
        side.addWidget(self.instruction)
        self.steps = label("", "steps", wrap=True)
        self.steps.setTextFormat(Qt.TextFormat.RichText)
        side.addWidget(self.steps)
        help_row = QHBoxLayout()
        self.auto_btn = button("Auto-detect", "primary",
                               tooltip="Let Gleaner find the list, its fields, the item link and the next page")
        self.auto_btn.clicked.connect(self._auto_detect)
        help_row.addWidget(self.auto_btn)
        help_row.addStretch(1)
        self.help_btn = button("How does this work?", tooltip="Step-by-step guide to making a recipe")
        self.help_btn.clicked.connect(lambda: self.help_requested.emit("builder"))
        help_row.addWidget(self.help_btn)
        side.addLayout(help_row)

        side.addWidget(label("List page", "h2"))
        row = QHBoxLayout()
        self.add_list_btn = button("+ Add list field")
        self.link_btn = button("Mark item link", tooltip="The link that opens one item's own page")
        self.next_btn = button("Mark next page")
        for b in (self.add_list_btn, self.link_btn, self.next_btn):
            row.addWidget(b)
        side.addLayout(row)
        self.next_label = label("", "hint", wrap=True)
        side.addWidget(self.next_label)

        side.addWidget(label("Item page", "h2"))
        row = QHBoxLayout()
        self.open_detail_btn = button("Open an item")
        self.add_detail_btn = button("+ Add item field")
        self.back_btn = button("Back to list")
        for b in (self.open_detail_btn, self.add_detail_btn, self.back_btn):
            row.addWidget(b)
        side.addLayout(row)

        side.addWidget(label("Fields", "h2"))
        self.fields_table = QTableWidget(0, 5)
        self.fields_table.setMinimumHeight(150)
        self.fields_table.setHorizontalHeaderLabels(["Page", "Column name", "Type", "Required", "Found"])
        self.fields_table.verticalHeader().hide()
        self.fields_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.fields_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.fields_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.fields_table.setColumnWidth(2, 92)
        self.fields_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.fields_table.itemChanged.connect(self._on_field_edited)
        self.fields_table.itemSelectionChanged.connect(self._show_selected)
        side.addWidget(self.fields_table, 1)
        row = QHBoxLayout()
        self.again_btn = button("Pick again", tooltip="Click another example to fix what this field finds")
        self.remove_btn = button("Remove field")
        row.addWidget(self.again_btn)
        row.addWidget(self.remove_btn)
        row.addStretch(1)
        side.addLayout(row)
        side.addWidget(label("Start pages", "h2"))
        side.addWidget(label("Gleaner starts at each of these list pages, for example one per city. Empty means the "
                             "page you are on.", "hint", wrap=True))
        self.starts_list = QListWidget()
        self.starts_list.setMaximumHeight(78)
        self.starts_list.setAccessibleName("Start pages")
        side.addWidget(self.starts_list)
        row = QHBoxLayout()
        self.add_start_btn = button("+ Add this page")
        self.paste_starts_btn = button("Paste addresses...")
        self.remove_start_btn = button("Remove")
        for b in (self.add_start_btn, self.paste_starts_btn, self.remove_start_btn):
            row.addWidget(b)
        row.addStretch(1)
        side.addLayout(row)
        self.add_start_btn.clicked.connect(self._add_start_page)
        self.paste_starts_btn.clicked.connect(self._paste_start_pages)
        self.remove_start_btn.clicked.connect(self._remove_start_page)
        self.save_btn = button("Save recipe", "primary")

        horizontal = QSplitter(Qt.Orientation.Horizontal)
        horizontal.addWidget(self.view)
        # The panel scrolls rather than squashing the steps and fields on small screens.
        panel_scroll = QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        panel_scroll.setWidget(panel)
        panel.setObjectName("view")
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(panel_scroll, 1)
        save_row = QHBoxLayout()
        save_row.setContentsMargins(12, 6, 0, 0)
        save_row.addWidget(self.save_btn)
        right_layout.addLayout(save_row)
        horizontal.addWidget(right)
        horizontal.setStretchFactor(0, 65)
        horizontal.setStretchFactor(1, 35)
        horizontal.setSizes([720, 480])
        panel.setMinimumWidth(440)

        preview = QWidget()
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(0, 8, 0, 0)
        prow = QHBoxLayout()
        self.preview_label = label("Preview", "h2")
        prow.addWidget(self.preview_label)
        prow.addStretch(1)
        self.preview_details_btn = button("Preview item pages",
                                          tooltip="Fetches 3 item pages politely (about 30 seconds)")
        prow.addWidget(self.preview_details_btn)
        pv.addLayout(prow)
        self.preview_table = QTableWidget(0, 0)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.verticalHeader().hide()
        pv.addWidget(self.preview_table)

        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.addWidget(horizontal)
        vertical.addWidget(preview)
        vertical.setStretchFactor(0, 3)
        vertical.setStretchFactor(1, 1)
        vertical.setSizes([600, 200])
        root.addWidget(vertical, 1)

        self.add_list_btn.clicked.connect(self._add_list_field)
        self.link_btn.clicked.connect(self._mark_link)
        self.next_btn.clicked.connect(self._mark_next)
        self.open_detail_btn.clicked.connect(self._open_sample_detail)
        self.add_detail_btn.clicked.connect(self._add_detail_field)
        self.back_btn.clicked.connect(self._back_to_list)
        self.again_btn.clicked.connect(self._pick_again)
        self.remove_btn.clicked.connect(self._remove_field)
        self.save_btn.clicked.connect(self._save)
        self.preview_details_btn.clicked.connect(self._preview_details)

    # ---- state -------------------------------------------------------------------------------

    def new_recipe(self):
        self.recipe_id = None
        self.max_records = 0
        self.item_selector = None
        self.fields: list[BuilderField] = []
        self.pagination = Pagination()
        self.start_urls: list[str] = []
        self.list_url = None
        self.list_html = None
        self.list_snapshot_url = None
        self.on_detail = False
        self.loaded = False
        self.pending = None
        self.dirty = False
        self.name_edit.clear()
        self.url_edit.clear()
        self._target_url = None
        self.view.setUrl(QUrl("about:blank"))
        self._render_fields()
        self._render_pagination()
        self._render_start_pages()
        self._fill_preview([], [])
        self._instruct(INSTRUCTIONS["idle"])
        self._update_buttons()

    def load_recipe(self, recipe_id):
        recipe = self.store.get_recipe(recipe_id)
        self.new_recipe()
        self.recipe_id = recipe_id
        self.max_records = recipe.max_records
        self.item_selector = recipe.item_selector
        link = recipe.detail.link_field if recipe.detail else None
        self.fields = [BuilderField("list", f, found="saved", is_link=f.name == link) for f in recipe.list_fields]
        if recipe.detail:
            self.fields += [BuilderField("detail", f, found="saved") for f in recipe.detail.fields]
        self.pagination = recipe.pagination
        self.start_urls = list(recipe.start_urls)
        self.name_edit.setText(recipe.name)
        self.url_edit.setText(recipe.start_url)
        self._render_fields()
        self._render_pagination()
        self._render_start_pages()
        self.dirty = False
        self.open_url()

    def confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        answer = QMessageBox.question(self, "Unsaved recipe", "This recipe has unsaved changes. Discard them?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def build_recipe(self) -> Recipe:
        list_fields = [b.field for b in self.fields if b.page == "list"]
        detail_fields = [b.field for b in self.fields if b.page == "detail"]
        link = next((b.field.name for b in self.fields if b.is_link), None)
        phones = [f.name for f in list_fields + detail_fields if f.type == "phone"]
        dedup = [list_fields[0].name, phones[0]] if phones and list_fields and list_fields[0].name != phones[0] else []
        pages = self.start_urls or [self.list_url or self.url_edit.text().strip()]
        return Recipe(
            name=self.name_edit.text().strip(),
            start_url=pages[0],
            start_urls=list(pages) if len(pages) > 1 else [],
            item_selector=self.item_selector or "",
            list_fields=list_fields,
            pagination=self.pagination,
            detail=Detail(link, detail_fields) if link and detail_fields else None,
            dedup_keys=dedup,
            max_records=self.max_records,
        )

    # ---- navigation --------------------------------------------------------------------------

    def open_url(self):
        url = self.url_edit.text().strip()
        if url and "://" not in url:
            url = "https://" + url
            self.url_edit.setText(url)
        problem = check_url(url, self.allow_local)
        if problem:
            self._instruct(f"That address can't be used: {problem}.", error=True)
            return
        self.open_btn.setEnabled(False)
        self._instruct("Checking the site's robots rules...")
        run_task(with_store(_robots_allows), url,
                 on_done=lambda allowed: self._robots_checked(url, allowed),
                 on_failed=self._robots_failed)

    def _robots_checked(self, url, allowed):
        self.open_btn.setEnabled(True)
        if not allowed:
            self._instruct("This site asks robots not to collect this page. Gleaner won't collect it.", error=True)
            return
        if not self.name_edit.text().strip():
            self.name_edit.setText(urlsplit(url).hostname or "")
        self.list_url = url
        self._navigate(url, detail=False)

    def _robots_failed(self, message):
        self.open_btn.setEnabled(True)
        self._instruct(message, error=True)

    def _on_load_started(self):
        self.loaded = False
        self._update_buttons()
        self.preview_label.setText("Preview - loading page...")

    def _on_loaded(self, ok):
        url = self.page.url().toString()
        if url == "about:blank":
            # A navigation requested while the blank page was still loading can be dropped by the engine;
            # ask for it again once the blank page is done.
            if self._target_url:
                QTimer.singleShot(0, lambda: self.view.setUrl(QUrl(self._target_url)))
            return
        if not ok:
            self._instruct("Couldn't open this page. Check the address and your internet.", error=True)
            return
        self.loaded = True
        if not self.on_detail:
            self.list_url = url
            if self.item_selector:
                self._instruct("Page ready. Select a field in the table to see what it finds, or add more.")
            else:
                self._instruct(INSTRUCTIONS["idle"])
        else:
            self._instruct("This is one item's page. Click + Add item field, then click a value.")
        self._update_buttons()
        self._refresh_preview()

    def _on_url_changed(self, qurl):
        if not self.on_detail and qurl.toString() != "about:blank":
            self.url_edit.setText(qurl.toString())

    def _navigate(self, url, detail):
        # Not "loaded" until loadFinished, so a quick click can't act on the page we are leaving.
        self.loaded = False
        self.on_detail = detail
        self._target_url = url
        self._update_buttons()
        self.view.setUrl(QUrl(url))

    def _go_detail(self, url):
        self._navigate(url, detail=True)

    def _sample_detail_url(self):
        recipe = self.build_recipe()
        link = next((b.field.name for b in self.fields if b.is_link), None)
        if not (link and self.list_html and recipe.item_selector):
            return None
        rows = self._safe_list(self.list_html, recipe, self.list_snapshot_url)
        return next((r.get(link) for r in rows if r.get(link)), None)

    def _open_sample_detail(self):
        url = self._sample_detail_url()
        if url:
            self._go_detail(url)
        else:
            self._instruct("Mark the item link on the list page first.", error=True)

    def _back_to_list(self):
        if self.list_url:
            self._navigate(self.list_url, detail=False)

    # ---- picking -----------------------------------------------------------------------------

    def _start(self, mode, row=None, **options):
        if not self.loaded:
            self._instruct("Open a page first, and wait for it to finish loading.", error=True)
            return
        self.pending = (mode, row)
        self.page.start_pick(mode, **options)
        self._instruct(INSTRUCTIONS[mode])
        self.view.setFocus()

    def _add_list_field(self):
        self._start("list", itemSelector=self.item_selector)

    def _mark_link(self):
        row = next((i for i, b in enumerate(self.fields) if b.is_link), None)
        self._start("link", row, itemSelector=self.item_selector)

    def _mark_next(self):
        self._start("next")

    def _add_detail_field(self):
        self._start("detail")

    def _pick_again(self):
        row = self.fields_table.currentRow()
        if row < 0 or row >= len(self.fields):
            return
        b = self.fields[row]
        if b.page == "detail":
            if not self.on_detail:
                self._instruct("Open the sample item page first, then click Pick again.", error=True)
                return
            self._start("detail", row)
        elif self.on_detail:
            self._instruct("Go back to the list page first, then click Pick again.", error=True)
        else:
            self._start("link" if b.is_link else "list", row, itemSelector=self.item_selector,
                        refineSteps=b.steps)

    def _on_picked(self, p):
        _mode, row = self.pending or (None, None)
        self.pending = None
        kind = p.get("type")
        if kind == "cancel":
            self._instruct("Picking cancelled.")
            return
        if kind == "error":
            self._instruct(p.get("message", "That didn't work. Try clicking something else."), error=True)
            return
        if kind in ("list", "link"):
            self.item_selector = p["itemSelector"]
            found = f"{p['count']} of {p['items']} items"
            sample = p.get("sample")
            if kind == "list":
                if row is not None:
                    b = self.fields[row]
                    b.field.selector, b.steps, b.found = p["selector"], p["steps"], found
                else:
                    name = self._unique_name(p.get("hint") or "Field")
                    if not self._sensitive_ok(name, sample):
                        return
                    self.fields.append(BuilderField("list", Field(name, p["selector"], type=guess_type(sample)),
                                                    p["steps"], found))
                self._instruct(f"Got it: {found} have this. Rename the column in the table if you like, "
                               "then add the next field.")
            else:
                if row is not None:
                    b = self.fields[row]
                    b.field.selector, b.steps, b.found = p["selector"], p["steps"], found
                else:
                    self.fields.append(BuilderField(
                        "list", Field(self._unique_name("Item link"), p["selector"], attr="href", type="link"),
                        p["steps"], found, is_link=True))
                self._instruct("Item link set. Opening one item's page: click the values you want there.")
                self._go_detail(p["href"])
        elif kind == "next":
            self.pagination = Pagination(**p["pagination"])
            self._render_pagination()
            self._instruct("Next page set. Gleaner will go through every page.")
        elif kind == "detail":
            lab, sample = p.get("label"), p.get("sample")
            if row is None:
                name = self._unique_name(lab or "Item field")
                if not self._sensitive_ok(name, lab or sample):
                    return
                self.fields.append(BuilderField("detail", Field(name, type=guess_type(sample))))
                row = len(self.fields) - 1
            b = self.fields[row]
            if lab:
                b.field.label, b.field.label_scope, b.field.selector = lab, p["label_scope"], None
                b.found = f"next to '{lab}'"
            else:
                b.field.label = b.field.label_scope = None
                b.field.selector = p["selector"]
                b.found = "position on page"
            self._instruct("Got it. Add more item fields, or go Back to list.")
        self.dirty = True
        self._render_fields()
        self._update_buttons()
        self._refresh_preview()

    def _unique_name(self, base):
        names = {b.field.name for b in self.fields}
        base = base.strip().rstrip(":").strip() or "Field"
        if base not in names and base != "Field":
            return base
        n = 1
        while f"{base} {n}" in names:
            n += 1
        return f"{base} {n}"

    def _sensitive_ok(self, *texts):
        if not any(t and SENSITIVE.search(t) for t in texts):
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Sensitive personal data")
        box.setText("This looks like sensitive personal data (date of birth, ID or bank details).\n\n"
                    "Gleaner leaves it out unless your manager has approved collecting it.")
        leave = box.addButton("Leave it out", QMessageBox.ButtonRole.RejectRole)
        box.addButton("Keep (manager approved)", QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(leave)
        box.exec()
        if box.clickedButton() is leave:
            self._instruct("Left out. Pick a different value.")
            return False
        return True

    # ---- fields table ------------------------------------------------------------------------

    def _render_fields(self):
        t = self.fields_table
        t.blockSignals(True)
        t.setRowCount(len(self.fields))
        for r, b in enumerate(self.fields):
            page = "Item link" if b.is_link else ("List" if b.page == "list" else "Item page")
            fixed = QTableWidgetItem(page)
            fixed.setFlags(fixed.flags() & ~Qt.ItemFlag.ItemIsEditable)
            t.setItem(r, 0, fixed)
            t.setItem(r, 1, QTableWidgetItem(b.field.name))
            combo = QComboBox()
            for text, value in FIELD_TYPES:
                combo.addItem(text, value)
            combo.setCurrentIndex(next(i for i, (_t, v) in enumerate(FIELD_TYPES) if v == b.field.type))
            combo.currentIndexChanged.connect(lambda _i, row=r, c=combo: self._set_type(row, c.currentData()))
            t.setCellWidget(r, 2, combo)
            req = QTableWidgetItem()
            req.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            req.setCheckState(Qt.CheckState.Checked if b.field.required else Qt.CheckState.Unchecked)
            t.setItem(r, 3, req)
            found = QTableWidgetItem(b.found)
            found.setFlags(found.flags() & ~Qt.ItemFlag.ItemIsEditable)
            t.setItem(r, 4, found)
        t.blockSignals(False)

    def _set_type(self, row, value):
        self.fields[row].field.type = value
        self.dirty = True
        self._refresh_preview()

    def _on_field_edited(self, item):
        row = item.row()
        if row >= len(self.fields):
            return
        f = self.fields[row].field
        if item.column() == 1:
            new = item.text().strip()
            others = {b.field.name for i, b in enumerate(self.fields) if i != row}
            if not new or new in others:
                self._instruct("Each column needs a different, non-empty name.", error=True)
                self.fields_table.blockSignals(True)
                item.setText(f.name)
                self.fields_table.blockSignals(False)
                return
            f.name = new
        elif item.column() == 3:
            f.required = item.checkState() == Qt.CheckState.Checked
        self.dirty = True
        self._refresh_preview()

    def _show_selected(self):
        row = self.fields_table.currentRow()
        if not self.loaded or row < 0 or row >= len(self.fields):
            return
        b = self.fields[row]
        if b.page == "list" and not self.on_detail and self.item_selector and b.field.selector is not None:
            self.page.show_list(self.item_selector, b.field.selector)
        elif b.page == "detail" and self.on_detail and b.field.selector:
            self.page.show_one(b.field.selector)
        else:
            self.page.clear_highlights()

    def _remove_field(self):
        row = self.fields_table.currentRow()
        if row < 0 or row >= len(self.fields):
            return
        b = self.fields[row]
        if b.is_link and any(x.page == "detail" for x in self.fields):
            answer = QMessageBox.question(self, "Remove item link?",
                                          "Removing the item link also removes all item fields. Continue?")
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.fields = [x for x in self.fields if x.page != "detail"]
        self.fields.remove(b)
        if not any(x.page == "list" for x in self.fields):
            self.item_selector = None
        self.dirty = True
        self.page.clear_highlights()
        self._render_fields()
        self._update_buttons()
        self._refresh_preview()

    def _render_pagination(self):
        p = self.pagination
        if p.type == "page_param":
            text = f"Next page: by page number ('{p.param}' = {p.start + 1}, {p.start + 2}, ...)."
        elif p.type == "next_link":
            text = f"Next page: the '{p.text}' link." if p.text else "Next page: the marked link."
        else:
            text = "Only this page will be collected (no next page marked)."
        self.next_label.setText(text)

    # ---- preview -----------------------------------------------------------------------------

    @staticmethod
    def _safe_list(html, recipe, url):
        try:
            return extract_list(html, recipe, url)
        except Exception:  # an unusual selector the parser rejects: no preview, not a crash
            log.exception("preview extraction failed")
            return []

    def _refresh_preview(self):
        if not self.loaded:
            return
        recipe = self.build_recipe()
        url = self.page.url().toString()

        def got(html):
            if self.on_detail:
                fields = [b.field for b in self.fields if b.page == "detail"]
                if not fields:
                    self._fill_preview([], [])
                    self.preview_label.setText("Preview - add item fields to see them here")
                    return
                recipe.detail = Detail("x", fields)
                try:
                    rows = [extract_detail(html, recipe, url)]
                except Exception:
                    log.exception("preview extraction failed")
                    rows = []
                self._fill_preview([f.name for f in fields], rows)
                self.preview_label.setText("Preview - this item page")
                return
            self.list_html, self.list_snapshot_url = html, url
            if not recipe.item_selector or not recipe.list_fields:
                self._fill_preview([], [])
                self.preview_label.setText("Preview - add a list field to see items here")
                return
            rows = self._safe_list(html, recipe, url)
            self._fill_preview([f.name for f in recipe.list_fields], rows[:PREVIEW_ROWS])
            self.preview_label.setText(f"Preview - {len(rows)} items on this page (first {PREVIEW_ROWS} shown)")
            self._update_buttons()

        self.page.snapshot(got)

    def _fill_preview(self, columns, rows):
        t = self.preview_table
        t.clear()
        t.setColumnCount(len(columns))
        t.setHorizontalHeaderLabels(columns)
        t.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, col in enumerate(columns):
                t.setItem(r, c, QTableWidgetItem(row.get(col) or ""))  # plain text only, never HTML
        t.resizeColumnsToContents()

    def _preview_details(self):
        recipe = self.build_recipe()
        if not recipe.detail or not self.list_html:
            self._instruct("Mark the item link and add item fields first (on the list page).", error=True)
            return
        rows = self._safe_list(self.list_html, recipe, self.list_snapshot_url)[:3]
        links = [r.get(recipe.detail.link_field) for r in rows if r.get(recipe.detail.link_field)]
        if not links:
            self._instruct("No item page links found on the list page.", error=True)
            return
        self.preview_details_btn.setEnabled(False)
        self.preview_label.setText(f"Preview - fetching {len(links)} item pages politely (about "
                                   f"{len(links) * 8} seconds)...")
        run_task(with_store(_fetch_details), recipe, links,
                 on_done=lambda details: self._details_previewed(recipe, rows, details),
                 on_failed=self._details_failed)

    def _details_previewed(self, recipe, rows, details):
        self.preview_details_btn.setEnabled(True)
        columns = [f.name for f in recipe.all_fields()]
        self._fill_preview(columns, [{**row, **d} for row, d in zip(rows, details)])
        self.preview_label.setText("Preview - first items with their item page values")

    def _details_failed(self, message):
        self.preview_details_btn.setEnabled(True)
        self.preview_label.setText("Preview")
        self._instruct(message, error=True)

    # ---- save --------------------------------------------------------------------------------

    def _save(self):
        recipe = self.build_recipe()
        try:
            validate(recipe, self.allow_local)
        except RecipeError as exc:
            problems = sorted({FRIENDLY_PROBLEMS.get(p, p) for p in exc.problems})
            self._instruct("Can't save yet:\n- " + "\n- ".join(problems), error=True)
            return
        existing = self.store.find_recipe(recipe.name)
        if existing is not None and existing != self.recipe_id:
            self._instruct(f"A recipe called '{recipe.name}' already exists. Choose another name.", error=True)
            return
        self.save_btn.setEnabled(False)
        self._instruct("Checking that the list can be read without the browser (one polite request)...")
        run_task(with_store(_raw_item_count), recipe,
                 on_done=lambda count: self._raw_checked(recipe, count), on_failed=self._save_failed)

    def _raw_checked(self, recipe, count):
        self.save_btn.setEnabled(True)
        if count == 0:
            self._instruct("This site builds its list inside the browser with JavaScript. Gleaner can't collect "
                           "sites like this yet, so the recipe was not saved.", error=True)
            return
        self.recipe_id = self.store.save_recipe(recipe, self.recipe_id)
        self.dirty = False
        self._update_buttons()
        self._instruct(f"Saved. {count} items found on the first page. Run it from the Library.")
        self.saved.emit(self.recipe_id)

    def _save_failed(self, message):
        self.save_btn.setEnabled(True)
        self._instruct(message, error=True)

    # ---- helpers -----------------------------------------------------------------------------

    def _instruct(self, text, error=False):
        self.instruction.setText(text)
        self.instruction.setProperty("state", "error" if error else "")
        restyle(self.instruction)

    def _render_steps(self):
        has_list = any(b.page == "list" and not b.is_link for b in self.fields)
        has_link = any(b.is_link for b in self.fields)
        has_detail = any(b.page == "detail" for b in self.fields)
        steps = [
            (bool(self.list_url), "Open the page that lists the items"),
            (has_list, "Add at least one list field"),
            (self.pagination.type != "none", "Optional: mark next page"),
            (has_link and has_detail, "Optional: mark item link, then add item fields"),
            (self.recipe_id is not None and not self.dirty, "Name the recipe and save"),
        ]
        lines = [f"{'&#10003;' if done else '&#9675;'}&nbsp; {i}. {text}" for i, (done, text) in enumerate(steps, 1)]
        self.steps.setText("<b>Steps</b><br>" + "<br>".join(lines))

    # ---- auto-detect -------------------------------------------------------------------------

    def _auto_detect(self):
        if not self.loaded:
            self._instruct("Open a page first, and wait for it to finish loading.", error=True)
            return
        self._instruct("Looking for the list and its fields...")
        self.page.auto_detect("detail" if self.on_detail else "list", self._auto_detected)

    def _auto_detected(self, res):
        kind = res.get("type")
        if kind == "error":
            self._instruct(res.get("message", "Auto-detect found nothing. Pick the fields by hand."), error=True)
            return
        left_out = []
        if kind == "auto":
            if any(b.page == "list" for b in self.fields):
                answer = QMessageBox.question(self, "Replace list fields?",
                                              "Auto-detect replaces the list fields you picked. Item page fields "
                                              "are kept. Continue?")
                if answer != QMessageBox.StandardButton.Yes:
                    self._instruct("Auto-detect cancelled.")
                    return
                self.fields = [b for b in self.fields if b.page == "detail"]
            self.item_selector = res["itemSelector"]
            for f in res["fields"]:
                sample = (f.get("samples") or [""])[0]
                name = self._unique_name(f.get("name") or "Field")
                if SENSITIVE.search(name) or SENSITIVE.search(sample):
                    left_out.append(name)
                    continue
                self.fields.append(BuilderField("list", Field(name, f["selector"], type=guess_type(sample)),
                                                f["steps"], "auto-detected"))
            added = sum(1 for b in self.fields if b.page == "list")
            if res.get("link"):
                link = res["link"]
                self.fields.append(BuilderField("list", Field(self._unique_name("Item link"), link["selector"],
                                                              attr="href", type="link"),
                                                link["steps"], "auto-detected", is_link=True))
            if res.get("pagination") and self.pagination.type == "none":
                self.pagination = Pagination(**res["pagination"])
                self._render_pagination()
            message = f"Found {res['items']} items with {added} fields."
            if res.get("link"):
                message += " Each item has its own page: click Open an item, then Auto-detect again there."
            if self.pagination.type != "none":
                message += " Next page found."
            self.page.show_list(self.item_selector)
        else:
            known = {b.field.label for b in self.fields if b.page == "detail"}
            added = 0
            for f in res["fields"]:
                if f["label"] in known:
                    continue
                name = self._unique_name(f["label"])
                if SENSITIVE.search(name) or SENSITIVE.search(f.get("sample") or ""):
                    left_out.append(f["label"])
                    continue
                self.fields.append(BuilderField(
                    "detail", Field(name, label=f["label"], label_scope=f["label_scope"],
                                    type=guess_type(f.get("sample"))), found=f"next to '{f['label']}'"))
                added += 1
            message = f"Found {added} item fields."
        if left_out:
            message += f" Left out as sensitive personal data: {', '.join(left_out)}."
        message += " Check the preview, remove what you don't need and rename columns."
        self._instruct(message)
        self.dirty = True
        self._render_fields()
        self._update_buttons()
        self._refresh_preview()

    # ---- start pages -------------------------------------------------------------------------

    def _render_start_pages(self):
        self.starts_list.clear()
        self.starts_list.addItems(self.start_urls)

    def _add_start_page(self):
        if not (self.loaded and not self.on_detail and self.list_url):
            self._instruct("Go to a list page first, then click + Add this page.", error=True)
            return
        if self.list_url in self.start_urls:
            self._instruct("This page is already a start page.")
            return
        self.start_urls.append(self.list_url)
        self.dirty = True
        self._render_start_pages()
        self._instruct(f"Start page added ({len(self.start_urls)} in total). Go to another list page in the "
                       "browser and add it too, or paste a list of addresses.")
        self._update_buttons()

    def _paste_start_pages(self):
        text, ok = QInputDialog.getMultiLineText(self, "Start pages", "Paste the addresses of list pages, one per line:")
        if not ok:
            return
        added, bad = 0, 0
        for line in (x.strip() for x in text.splitlines()):
            if not line:
                continue
            if check_url(line, self.allow_local):
                bad += 1
            elif line not in self.start_urls:
                self.start_urls.append(line)
                added += 1
        self.dirty = self.dirty or added > 0
        self._render_start_pages()
        message = f"Added {added} start pages."
        if bad:
            message += f" {bad} lines were not usable web addresses and were skipped."
        self._instruct(message, error=bool(bad and not added))
        self._update_buttons()

    def _remove_start_page(self):
        row = self.starts_list.currentRow()
        if 0 <= row < len(self.start_urls):
            del self.start_urls[row]
            self.dirty = True
            self._render_start_pages()
            self._update_buttons()

    def _update_buttons(self):
        self._render_steps()
        on_list = self.loaded and not self.on_detail
        self.auto_btn.setEnabled(self.loaded)
        self.add_start_btn.setEnabled(on_list)
        self.remove_start_btn.setEnabled(bool(self.start_urls))
        has_link = any(b.is_link for b in self.fields)
        self.add_list_btn.setEnabled(on_list)
        self.link_btn.setEnabled(on_list)
        self.next_btn.setEnabled(on_list)
        self.open_detail_btn.setEnabled(on_list and has_link)
        self.add_detail_btn.setEnabled(self.loaded and self.on_detail)
        self.back_btn.setEnabled(self.on_detail)
        self.preview_details_btn.setEnabled(on_list and has_link and any(b.page == "detail" for b in self.fields))
        self.again_btn.setEnabled(self.loaded and bool(self.fields))
        self.remove_btn.setEnabled(bool(self.fields))
