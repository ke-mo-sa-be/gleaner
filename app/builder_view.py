"""Recipe Builder: point and click on a website to teach Gleaner what to collect (UX Flows 1-3)."""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import shiboken6
from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QInputDialog, QLineEdit, QListWidget, QMessageBox, QScrollArea, QSizePolicy, QSplitter,
                               QStackedWidget, QTabBar, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget)

from app import render, style
from app.tasks import run_task, with_store
from app.web import PickerPage
from app.widgets import button, glyph_icon, icon_button, label, restyle
from core.extract import extract_detail, extract_list
from core.fetcher import Fetcher
from core.recipe import Detail, Field, Pagination, Recipe, RecipeError, check_url, validate

log = logging.getLogger(__name__)

FIELD_TYPES = [("Text", "text"), ("Link", "link"), ("Image", "image"), ("Phone", "phone"), ("Email", "email"),
               ("Pincode", "pincode"), ("Number", "number")]
STEP_TABS = ("List", "Item page", "More pages")
LIST, ITEM, PAGES = range(3)
LIST_TYPES = [("Repeating items", "elements"), ("Headings with text below", "sections")]
COUNTRIES = [("India +91", "91"), ("Nigeria +234", "234"), ("Kenya +254", "254"), ("Ghana +233", "233"),
             ("South Africa +27", "27"), ("UAE +971", "971"), ("Saudi Arabia +966", "966"), ("UK +44", "44"),
             ("USA / Canada +1", "1"), ("Australia +61", "61"), ("Singapore +65", "65"),
             ("Bangladesh +880", "880"), ("Sri Lanka +94", "94"), ("Nepal +977", "977")]
SENSITIVE = re.compile(r"birth|\bdob\b|aadha?ar|\bpan\b|bank|account\s*(no|number)|ifsc|card\s*(no|number)", re.I)
EMAIL_LIKE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PREVIEW_ROWS = 10
SETTLE_MS = 1500  # second preview after load, for pages built by JavaScript

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


def type_for_label(label):
    """Column type for a 'Label: value' field, from the label's words."""
    text = (label or "").lower()
    if re.search(r"phone|tel|mobile|cell|whatsapp|contact no", text):
        return "phone"
    if re.search(r"e-?mail", text):
        return "email"
    if re.search(r"web|site|url", text):
        return "link"
    if re.search(r"pin ?code|postal|zip", text):
        return "pincode"
    return "text"


# Tests only: e.g. {"min_delay": 0, "max_delay": 0, "_min_delay_floor": 0} against the local fixture site.
FETCHER_OPTIONS = {}


def _fetcher(store):
    return Fetcher(store, renderer=render.renderer(), **FETCHER_OPTIONS)


def _robots_allows(store, url):
    return _fetcher(store).allowed(url)


def _raw_item_count(store, recipe):
    """Items found in the page as the server sends it (what a run sees), via one polite request."""
    html = _fetcher(store).get(recipe.start_url)
    return len(extract_list(html, recipe, recipe.start_url))


def _fetch_details(store, recipe, links):
    fetcher = _fetcher(store)
    return [extract_detail(fetcher.get(link, render=recipe.render_js), recipe, link) for link in links]


class BuilderView(QWidget):
    saved = Signal(int)
    help_requested = Signal(str)  # guide section key

    def __init__(self, store, parent=None, allow_local=False):
        super().__init__(parent)
        self.setObjectName("view")
        self.store = store
        self.allow_local = allow_local  # tests only (local fixture site)
        render.renderer()  # created here, on the UI thread; background checks use it for JavaScript sites
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
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # Browser bar, like a web browser's: back, forward, reload, address, Open.
        bar = QFrame()
        bar.setObjectName("card")
        top = QHBoxLayout(bar)
        top.setContentsMargins(6, 4, 6, 4)
        top.setSpacing(2)
        self.nav_back_btn = icon_button("back", "Back (Alt+Left)")
        self.nav_forward_btn = icon_button("forward", "Forward (Alt+Right)")
        self.reload_btn = icon_button("reload", "Reload this page")
        for b in (self.nav_back_btn, self.nav_forward_btn, self.reload_btn):
            top.addWidget(b)
        self.nav_back_btn.clicked.connect(self._nav_back)
        self.nav_forward_btn.clicked.connect(self._nav_forward)
        self.reload_btn.clicked.connect(self._reload)
        QShortcut(QKeySequence("Alt+Left"), self, activated=self._nav_back)
        QShortcut(QKeySequence("Alt+Right"), self, activated=self._nav_forward)
        self.url_edit = QLineEdit()
        self.url_edit.setObjectName("address")
        self.url_edit.setPlaceholderText("Website address, e.g. https://www.example.com/doctors")
        self.url_edit.setAccessibleName("Website address")
        self.url_edit.returnPressed.connect(self.open_url)
        top.addSpacing(6)
        top.addWidget(self.url_edit, 1)
        self.open_btn = button("Open", "primary")
        self.open_btn.clicked.connect(self.open_url)
        top.addWidget(self.open_btn)
        root.addWidget(bar)

        self.view = QWebEngineView()
        web_frame = QFrame()
        web_frame.setObjectName("card")
        wf = QVBoxLayout(web_frame)
        wf.setContentsMargins(1, 1, 1, 1)
        wf.addWidget(self.view)

        # ---- right panel: name, hint, steps as tabs, columns, options, save ----
        panel = QFrame()
        panel.setObjectName("card")
        side = QVBoxLayout(panel)
        side.setContentsMargins(16, 14, 16, 14)
        side.setSpacing(10)
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("title")
        self.name_edit.setPlaceholderText("Recipe name, e.g. Shops - Pune")
        self.name_edit.setAccessibleName("Recipe name")
        side.addWidget(self.name_edit)
        self.instruction = label(INSTRUCTIONS["idle"], "instruction", wrap=True)
        side.addWidget(self.instruction)

        self.tabs = QTabBar()
        self.tabs.setObjectName("steps")
        self.tabs.setExpanding(True)
        self.tabs.setDrawBase(False)
        for text in STEP_TABS:
            self.tabs.addTab(text)
        self.tabs.currentChanged.connect(self._tab_changed)
        side.addWidget(self.tabs)
        self.step_pages = QStackedWidget()
        side.addWidget(self.step_pages)

        # Step 1: list page
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.auto_btn = button("Auto-detect", "primary",
                               tooltip="Let Gleaner find the list, its fields, the item link and the next page")
        self.auto_btn.clicked.connect(self._auto_detect)
        self.add_list_btn = button("+ Add field", tooltip="Click a value on the page, e.g. a name")
        self.add_list_btn.setAccessibleName("Add list field")
        self.link_btn = button("Mark item link", tooltip="The link that opens one item's own page")
        for b in (self.auto_btn, self.add_list_btn, self.link_btn):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.step_pages.addWidget(page)

        # Step 2: item page
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        self.item_hint = label("Optional. If the list doesn't show everything, mark the item link on the List step, "
                               "then add values from one item's own page here.", "hint", wrap=True)
        lay.addWidget(self.item_hint)
        row = QHBoxLayout()
        self.open_detail_btn = button("Open an item")
        self.add_detail_btn = button("+ Add field", tooltip="Click a value on this item's page, e.g. the phone")
        self.add_detail_btn.setAccessibleName("Add item field")
        self.auto_detail_btn = button("Auto-detect", "primary", tooltip="Find every label and value on this page")
        self.auto_detail_btn.clicked.connect(self._auto_detect)
        self.back_btn = button("Back to list")
        for b in (self.open_detail_btn, self.auto_detail_btn, self.add_detail_btn, self.back_btn):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.step_pages.addWidget(page)

        # Step 3: more pages and start pages
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.next_btn = button("Mark next page", tooltip="Click the site's Next button or the link to page 2")
        row.addWidget(self.next_btn)
        self.next_label = label("", "hint", wrap=True)
        row.addWidget(self.next_label, 1)
        lay.addLayout(row)
        lay.addWidget(label("Start pages: Gleaner starts at each of these lists, for example one per city. Empty "
                            "means the page you are on.", "hint", wrap=True))
        self.starts_list = QListWidget()
        self.starts_list.setObjectName("plain")
        self.starts_list.setMaximumHeight(96)
        self.starts_list.setAccessibleName("Start pages")
        lay.addWidget(self.starts_list)
        row = QHBoxLayout()
        self.add_start_btn = button("+ Add this page")
        self.paste_starts_btn = button("Paste addresses...")
        self.remove_start_btn = button("Remove", "quiet")
        for b in (self.add_start_btn, self.paste_starts_btn, self.remove_start_btn):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.add_start_btn.clicked.connect(self._add_start_page)
        self.paste_starts_btn.clicked.connect(self._paste_start_pages)
        self.remove_start_btn.clicked.connect(self._remove_start_page)
        self.step_pages.addWidget(page)
        self.step_pages.currentChanged.connect(lambda _i: self._fit_step_pages())

        # Columns of the current step
        head = QHBoxLayout()
        self.columns_label = label("Columns", "h2")
        head.addWidget(self.columns_label)
        head.addStretch(1)
        self.again_btn = button("Pick again", "quiet", tooltip="Click another example to fix what this column finds")
        self.remove_btn = button("Remove", "quiet")
        self.remove_btn.setAccessibleName("Remove field")
        head.addWidget(self.again_btn)
        head.addWidget(self.remove_btn)
        self.columns_head = QWidget()
        self.columns_head.setLayout(head)
        head.setContentsMargins(0, 4, 0, 0)
        side.addWidget(self.columns_head)
        self._rows = []  # table row -> index in self.fields (the table shows the current step's columns)
        self.fields_table = QTableWidget(0, 3)
        self.fields_table.setObjectName("plain")
        self.fields_table.setHorizontalHeaderLabels(["Column", "Type", "Required"])
        self.fields_table.verticalHeader().hide()
        self.fields_table.verticalHeader().setDefaultSectionSize(36)
        self.fields_table.setShowGrid(False)
        self.fields_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.fields_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.fields_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.fields_table.setColumnWidth(1, 104)
        self.fields_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.fields_table.itemChanged.connect(self._on_field_edited)
        self.fields_table.itemSelectionChanged.connect(self._show_selected)
        side.addWidget(self.fields_table, 10)
        self.empty_columns = label("", "hint", wrap=True)
        side.addWidget(self.empty_columns)
        side.addStretch(1)  # keeps the options and Save at the bottom when there is no table

        # Options, closed by default: list type and phone country
        self.options_btn = QToolButton()
        self.options_btn.setObjectName("disclosure")
        self.options_btn.setCheckable(True)
        self.options_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.options_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.options_btn.setText("Options")
        self.options_btn.toggled.connect(self._toggle_options)
        side.addWidget(self.options_btn)
        self.options = QWidget()
        grid = QGridLayout(self.options)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(label("List type"), 0, 0)
        self.list_type = QComboBox()
        for text, value in LIST_TYPES:
            self.list_type.addItem(text, value)
        self.list_type.setToolTip("Headings with text below: each heading (for example a company name) starts an "
                                  "item, and the paragraphs under it belong to it")
        self.list_type.activated.connect(self._list_type_chosen)
        grid.addWidget(self.list_type, 0, 1)
        grid.addWidget(label("Phone country"), 1, 0)
        self.country = QComboBox()
        for text, value in COUNTRIES:
            self.country.addItem(text, value)
        self.country.addItem("Other...", "other")
        self.country.setToolTip("Used for phone numbers written without a country code")
        self.country.activated.connect(self._country_chosen)
        grid.addWidget(self.country, 1, 1)
        grid.setColumnStretch(1, 1)
        self.options.hide()
        side.addWidget(self.options)

        foot = QHBoxLayout()
        self.help_btn = button("How does this work?", "link", tooltip="Step-by-step guide to making a recipe")
        self.help_btn.clicked.connect(lambda: self.help_requested.emit("builder"))
        foot.addWidget(self.help_btn)
        foot.addStretch(1)
        self.save_btn = button("Save recipe", "primary")
        foot.addWidget(self.save_btn)
        side.addLayout(foot)

        panel_scroll = QScrollArea()  # scrolls rather than squashing on small screens
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        panel_scroll.setWidget(panel)
        panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel_scroll.setMinimumWidth(440)

        horizontal = QSplitter(Qt.Orientation.Horizontal)
        horizontal.setHandleWidth(10)
        horizontal.addWidget(web_frame)
        horizontal.addWidget(panel_scroll)
        horizontal.setStretchFactor(0, 65)
        horizontal.setStretchFactor(1, 35)
        horizontal.setSizes([740, 470])

        # ---- preview, collapsible ----
        preview = QFrame()
        preview.setObjectName("card")
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(12, 6, 12, 8)
        prow = QHBoxLayout()
        self.preview_btn = QToolButton()
        self.preview_btn.setObjectName("disclosure")
        self.preview_btn.setCheckable(True)
        self.preview_btn.setChecked(True)
        self.preview_btn.setArrowType(Qt.ArrowType.DownArrow)
        self.preview_btn.setToolTip("Show or hide the preview")
        self.preview_btn.setAccessibleName("Hide preview")
        self.preview_btn.toggled.connect(self._toggle_preview)
        prow.addWidget(self.preview_btn)
        self.preview_label = label("Preview", "h2")
        prow.addWidget(self.preview_label)
        prow.addStretch(1)
        self.preview_details_btn = button("Preview item pages", "quiet",
                                          tooltip="Fetches 3 item pages politely (about 30 seconds)")
        prow.addWidget(self.preview_details_btn)
        pv.addLayout(prow)
        self.preview_table = QTableWidget(0, 0)
        self.preview_table.setObjectName("plain")
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.verticalHeader().hide()
        self.preview_table.setShowGrid(False)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.preview_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.preview_table.setToolTip("Click a row to find that item on the page")
        self.preview_table.itemSelectionChanged.connect(self._show_preview_row)
        pv.addWidget(self.preview_table)

        self.vertical = QSplitter(Qt.Orientation.Vertical)
        self.vertical.setHandleWidth(10)
        self.vertical.addWidget(horizontal)
        self.vertical.addWidget(preview)
        self.vertical.setStretchFactor(0, 3)
        self.vertical.setStretchFactor(1, 1)
        self.vertical.setSizes([600, 220])
        root.addWidget(self.vertical, 1)

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
        style.theme_changed.changed.connect(self._restyle_icons)
        self._fit_step_pages()

    def _restyle_icons(self):
        for b in (self.nav_back_btn, self.nav_forward_btn, self.reload_btn):
            b.setIcon(glyph_icon(b.property("glyph"), "MUTED"))
        self._render_fields()

    def _fit_step_pages(self):
        """The step area takes the height of the visible step only."""
        current = self.step_pages.currentWidget()
        for i in range(self.step_pages.count()):
            policy = QSizePolicy.Policy.Preferred if i == self.step_pages.currentIndex() else QSizePolicy.Policy.Ignored
            self.step_pages.widget(i).setSizePolicy(QSizePolicy.Policy.Preferred, policy)
        current.layout().activate()
        self.step_pages.setFixedHeight(current.layout().heightForWidth(max(self.step_pages.width(), 380))
                                       if current.layout().hasHeightForWidth() else current.sizeHint().height())

    def _toggle_options(self, shown):
        self.options.setVisible(shown)
        self.options_btn.setArrowType(Qt.ArrowType.DownArrow if shown else Qt.ArrowType.RightArrow)

    def _toggle_preview(self, shown):
        self.preview_table.setVisible(shown)
        self.preview_btn.setArrowType(Qt.ArrowType.DownArrow if shown else Qt.ArrowType.RightArrow)
        self.preview_btn.setAccessibleName("Hide preview" if shown else "Show preview")
        total = sum(self.vertical.sizes())
        self.vertical.setSizes([total - 220, 220] if shown else [total - 44, 44])

    def _tab_changed(self, index):
        self.step_pages.setCurrentIndex(index)
        self._render_fields()
        self._update_buttons()

    # ---- state -------------------------------------------------------------------------------

    def new_recipe(self):
        self.recipe_id = None
        self.max_records = 0
        self.item_selector = None
        self.item_mode = "elements"
        self.phone_country = "91"
        self.render_js = False
        self._last_detail_url = None
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
        self._render_list_options()
        self._fill_preview([], [])
        self._instruct(INSTRUCTIONS["idle"])
        self._update_buttons()

    def load_recipe(self, recipe_id):
        recipe = self.store.get_recipe(recipe_id)
        self.new_recipe()
        self.recipe_id = recipe_id
        self.max_records = recipe.max_records
        self.item_selector = recipe.item_selector
        self.item_mode = recipe.item_mode
        self.phone_country = recipe.phone_country
        self.render_js = recipe.render_js
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
        self._render_list_options()
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
            item_mode=self.item_mode,
            phone_country=self.phone_country,
            render_js=self.render_js,
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

    def _alive(self) -> bool:
        """False while the builder is being destroyed (closing the app): the page can still send signals."""
        return shiboken6.isValid(self) and shiboken6.isValid(self.view)

    def _on_load_started(self):
        if not self._alive():
            return
        self.loaded = False
        self._update_buttons()
        self.preview_label.setText("Preview - loading page..." if self._target_url or self.loaded else "Preview")

    def _on_loaded(self, ok):
        if not self._alive():
            return
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
            self._instruct("This is one item's page. Click + Add field, then click a value.")
        if self.on_detail:
            self.tabs.setCurrentIndex(ITEM)
        elif self.tabs.currentIndex() == ITEM:
            self.tabs.setCurrentIndex(LIST)
        self._update_buttons()
        self._refresh_preview()
        # Sites that build their content with JavaScript fill the page after it has loaded: look again.
        loaded_url = url
        QTimer.singleShot(SETTLE_MS, lambda: self.loaded and self.page.url().toString() == loaded_url
                          and self._refresh_preview())

    def _on_url_changed(self, qurl):
        if not self._alive():
            return
        if qurl.toString() != "about:blank":  # the address bar shows the page in the browser, like any browser
            self.url_edit.setText(qurl.toString())

    def _navigate(self, url, detail):
        # Not "loaded" until loadFinished, so a quick click can't act on the page we are leaving.
        self.loaded = False
        self.on_detail = detail
        self._target_url = url
        self._update_buttons()
        self.view.setUrl(QUrl(url))

    def _go_detail(self, url):
        self._last_detail_url = url
        self._navigate(url, detail=True)

    # ---- back / forward / reload -------------------------------------------------------------

    def _back_target(self):
        """The nearest earlier page that is a real, different page (not the blank start or a repeat)."""
        history = self.view.history()
        current = self.page.url().toString()
        for item in reversed(history.backItems(50)):
            url = item.url().toString()
            if url not in ("", "about:blank") and url != current:
                return item
        return None

    def _can_go_back(self):
        return self._back_target() is not None

    def _nav_back(self):
        item = self._back_target()
        if item is None:
            return
        self.loaded = False
        self._target_url = None
        self.on_detail = False  # back from an item page lands on the list
        self._update_buttons()
        self.view.history().goToItem(item)

    def _nav_forward(self):
        history = self.view.history()
        if not history.canGoForward():
            return
        target = history.forwardItem().url().toString()
        self.loaded = False
        self._target_url = None
        self.on_detail = bool(self._last_detail_url) and target == self._last_detail_url
        self._update_buttons()
        self.view.forward()

    def _reload(self):
        if self.page.url().toString() not in ("", "about:blank"):
            self.loaded = False
            self._update_buttons()
            self.view.reload()

    # ---- list type and phone country ---------------------------------------------------------

    def _render_list_options(self):
        self.list_type.setCurrentIndex(max(0, self.list_type.findData(self.item_mode)))
        index = self.country.findData(self.phone_country)
        if index < 0:
            self.country.insertItem(self.country.count() - 1, f"+{self.phone_country}", self.phone_country)
            index = self.country.findData(self.phone_country)
        self.country.setCurrentIndex(index)

    def _list_type_chosen(self, _index):
        mode = self.list_type.currentData()
        if mode == self.item_mode:
            return
        if any(b.page == "list" for b in self.fields):
            answer = QMessageBox.question(self, "Change list type?",
                                          "Changing the list type removes the list fields you picked. Item page "
                                          "fields are kept. Continue?")
            if answer != QMessageBox.StandardButton.Yes:
                self._render_list_options()
                return
            self.fields = [b for b in self.fields if b.page == "detail"]
        self.item_mode = mode
        self.item_selector = None
        self.dirty = True
        if self.loaded:
            self.page.clear_highlights()
        self._render_fields()
        self._update_buttons()
        self._refresh_preview()
        if mode == "sections":
            self._instruct("Headings with text below: click + Add list field, then click one heading (for example "
                           "a company name). Then add the text under it: the address, or a paragraph with "
                           "Phone: / Email: lines.")

    def _country_chosen(self, _index):
        value = self.country.currentData()
        if value == "other":
            code, ok = QInputDialog.getText(self, "Phone country", "Country calling code (digits only, e.g. 49):")
            code = (code or "").strip().lstrip("+")
            if not ok or not code.isdigit() or not 1 <= len(code) <= 3:
                self._render_list_options()
                return
            value = code
        if value != self.phone_country:
            self.phone_country = value
            self.dirty = True
            self._refresh_preview()
        self._render_list_options()

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
        self._start("list", itemSelector=self.item_selector, itemMode=self.item_mode)

    def _mark_link(self):
        row = next((i for i, b in enumerate(self.fields) if b.is_link), None)
        self._start("link", row, itemSelector=self.item_selector, itemMode=self.item_mode)

    def _mark_next(self):
        self._start("next")

    def _add_detail_field(self):
        self._start("detail")

    def _pick_again(self):
        row = self._selected_field()
        if row is None:
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
                        refineSteps=b.steps, itemMode=self.item_mode)

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
                elif p.get("labels") and p.get("itemMode") == "sections":
                    # "Email: ... / Phone: ..." lines in a section: one column per label.
                    added = []
                    for group in p["labels"]:  # {"name": "Phone", "label": "Phone|Tel"}
                        name, lab = group["name"], group["label"]
                        if any(b.field.label == lab for b in self.fields) or not self._sensitive_ok(name):
                            continue
                        self.fields.append(BuilderField("list", Field(self._unique_name(name), label=lab,
                                                                      type=type_for_label(name)),
                                                        None, "after " + ", ".join(f"'{x}:'" for x in lab.split("|"))))
                        added.append(name)
                    found = None
                    self._instruct(f"Added columns for: {', '.join(added) or 'nothing new'}. Remove the ones you "
                                   "don't need.")
                else:
                    image = p.get("attr") == "src"
                    name = self._unique_name(p.get("hint") or ("Image" if image else "Field"))
                    if not self._sensitive_ok(name, sample):
                        return
                    field = (Field(name, p["selector"], attr="src", type="image") if image
                             else Field(name, p["selector"], type=guess_type(sample)))
                    self.fields.append(BuilderField("list", field, p["steps"], found))
                if found:
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
        """The columns of the current step: list columns on List, item page columns on Item page."""
        step = self.tabs.currentIndex()
        page = "detail" if step == ITEM else "list"
        self._rows = [i for i, b in enumerate(self.fields) if b.page == page] if step != PAGES else []
        t = self.fields_table
        t.blockSignals(True)
        t.setRowCount(len(self._rows))
        for r, index in enumerate(self._rows):
            b = self.fields[index]
            name = QTableWidgetItem(b.field.name)
            name.setToolTip(("Item link. " if b.is_link else "") + (f"Found: {b.found}" if b.found else ""))
            if b.is_link:
                name.setIcon(glyph_icon("link", "MUTED", 16))
            t.setItem(r, 0, name)
            combo = QComboBox()
            combo.setObjectName("cell")
            for text, value in FIELD_TYPES:
                combo.addItem(text, value)
            combo.setCurrentIndex(next(i for i, (_t, v) in enumerate(FIELD_TYPES) if v == b.field.type))
            combo.currentIndexChanged.connect(lambda _i, row=index, c=combo: self._set_type(row, c.currentData()))
            t.setCellWidget(r, 1, combo)
            req = QTableWidgetItem()
            req.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            req.setCheckState(Qt.CheckState.Checked if b.field.required else Qt.CheckState.Unchecked)
            req.setToolTip("Rows without this value go to Needs Review")
            t.setItem(r, 2, req)
        t.blockSignals(False)
        empty = {LIST: "No columns yet. Click Auto-detect, or + Add field and click a value on the page.",
                 ITEM: "No item page columns yet."}
        shown = step != PAGES
        t.setVisible(shown and bool(self._rows))
        self.columns_head.setVisible(shown)
        self.empty_columns.setVisible(shown and not self._rows)
        self.empty_columns.setText(empty.get(step, ""))

    def _selected_field(self):
        """Index in self.fields of the selected table row, or None."""
        row = self.fields_table.currentRow()
        if not self.fields_table.selectedItems() or not 0 <= row < len(self._rows):
            return None
        return self._rows[row]

    def _set_type(self, row, value):
        self.fields[row].field.type = value
        self.dirty = True
        self._refresh_preview()

    def _on_field_edited(self, item):
        if item.row() >= len(self._rows):
            return
        row = self._rows[item.row()]
        f = self.fields[row].field
        if item.column() == 0:
            new = item.text().strip()
            others = {b.field.name for i, b in enumerate(self.fields) if i != row}
            if not new or new in others:
                self._instruct("Each column needs a different, non-empty name.", error=True)
                self.fields_table.blockSignals(True)
                item.setText(f.name)
                self.fields_table.blockSignals(False)
                return
            f.name = new
        elif item.column() == 2:
            f.required = item.checkState() == Qt.CheckState.Checked
        self.dirty = True
        self._refresh_preview()

    def _show_selected(self):
        row = self._selected_field()
        self._update_buttons()
        if not self.loaded or row is None:
            return
        b = self.fields[row]
        f = b.field

        def shown(count):  # the page has scrolled to the first match and flashes it
            self._shown(b, count)

        if b.page == "list" and not self.on_detail and self.item_selector and self.item_mode == "sections":
            self.page.show_section(self.item_selector, {"label": f.label} if f.label else {"selector": f.selector},
                                   shown)
        elif b.page == "list" and not self.on_detail and self.item_selector and f.selector is not None:
            self.page.show_list(self.item_selector, f.selector, shown)
        elif b.page == "detail" and self.on_detail and f.label and f.label_scope:
            self.page.show_label(f.label, f.label_scope, shown)
        elif b.page == "detail" and self.on_detail and f.selector:
            self.page.show_one(f.selector, shown)
        else:
            self.page.clear_highlights()
            where = "list page" if b.page == "list" else "item page"
            self._instruct(f"Open the {where} to see where '{f.name}' is.")

    def _shown(self, b, count):
        if not isinstance(count, (int, float)):
            return
        if count:
            self._instruct(f"'{b.field.name}' is outlined on the page ({int(count)} found). The flashing one is "
                           "the first.")
        else:
            self._instruct(f"'{b.field.name}' isn't on this page. Pick again to fix it, or Remove it.", error=True)

    def _show_preview_row(self):
        """Clicking a preview row scrolls the page to that item."""
        row = self.preview_table.currentRow()
        if row < 0 or not self.loaded or self.on_detail or not self.item_selector:
            return
        self.page.show_item(self.item_selector, row, self.item_mode == "sections")

    def _remove_field(self):
        row = self._selected_field()
        if row is None:
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
        # Items the builder's browser shows on this page. Far more than the plain page has means the site
        # builds its list with JavaScript: runs then open each page in Gleaner's browser.
        shown = len(self._safe_list(self.list_html, recipe, self.list_snapshot_url)) if self.list_html else 0
        recipe.render_js = shown > 0 and count < shown / 2
        if count == 0 and not recipe.render_js:
            self._instruct("No items found on the start page. Open the list page and check the preview.",
                           error=True)
            return
        self.render_js = recipe.render_js
        self.recipe_id = self.store.save_recipe(recipe, self.recipe_id)
        self.dirty = False
        self._update_buttons()
        if recipe.render_js:
            self._instruct(f"Saved. This site builds its list with JavaScript, so runs open each page in Gleaner's "
                           f"browser: {shown} items on this page, a little slower than usual. Run it from the "
                           "Library.")
        else:
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
        """A tick on each step that is done."""
        has_list = any(b.page == "list" and not b.is_link for b in self.fields)
        has_detail = any(b.page == "detail" for b in self.fields)
        done = (has_list, has_detail, self.pagination.type != "none" or bool(self.start_urls))
        for i, (text, ok) in enumerate(zip(STEP_TABS, done)):
            self.tabs.setTabText(i, f"\u2713 {text}" if ok else text)
            self.tabs.setTabToolTip(i, "Done" if ok else ("Optional" if i else "Start here"))

    # ---- auto-detect -------------------------------------------------------------------------

    def _auto_detect(self):
        if not self.loaded:
            self._instruct("Open a page first, and wait for it to finish loading.", error=True)
            return
        self._instruct("Looking for the list and its fields...")
        # A list type the user chose ("Headings with text below") is respected.
        self.page.auto_detect("detail" if self.on_detail else "list", self._auto_detected,
                              self.item_mode if self.item_mode == "sections" else None)

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
            self.item_mode = res.get("itemMode", "elements")
            self._render_list_options()
            for f in res["fields"]:
                sample = (f.get("samples") or [""])[0]
                name = self._unique_name(f.get("name") or "Field")
                if SENSITIVE.search(name) or SENSITIVE.search(sample):
                    left_out.append(name)
                    continue
                if f.get("label"):
                    field = Field(name, label=f["label"], type=type_for_label(f["label"]))
                else:
                    field = Field(name, f["selector"], attr=f.get("attr", "text"),
                                  type=f.get("type") or guess_type(sample))
                self.fields.append(BuilderField("list", field, f.get("steps"), "auto-detected"))
            added = sum(1 for b in self.fields if b.page == "list")
            if res.get("link"):
                link = res["link"]
                self.fields.append(BuilderField("list", Field(self._unique_name("Item link"), link["selector"],
                                                              attr="href", type="link"),
                                                link["steps"], "auto-detected", is_link=True))
            if res.get("pagination") and self.pagination.type == "none":
                self.pagination = Pagination(**res["pagination"])
                self._render_pagination()
            kind_text = "headings with text below" if self.item_mode == "sections" else "items"
            message = f"Found {res['items']} {kind_text} with {added} fields."
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
        self.nav_back_btn.setEnabled(self._can_go_back())
        self.nav_forward_btn.setEnabled(self.view.history().canGoForward())
        self.reload_btn.setEnabled(self.page.url().toString() not in ("", "about:blank")
                                   if hasattr(self, "page") else False)
        on_list = self.loaded and not self.on_detail
        has_link = any(b.is_link for b in self.fields)
        self.auto_btn.setEnabled(on_list)
        self.add_start_btn.setEnabled(on_list)
        self.remove_start_btn.setEnabled(bool(self.start_urls))
        self.add_list_btn.setEnabled(on_list)
        self.link_btn.setEnabled(on_list)
        self.next_btn.setEnabled(on_list)
        # Item page step: show only the buttons that make sense right now.
        self.open_detail_btn.setVisible(not self.on_detail)
        self.open_detail_btn.setEnabled(on_list and has_link)
        for b in (self.auto_detail_btn, self.add_detail_btn, self.back_btn):
            b.setVisible(self.on_detail)
        self.auto_detail_btn.setEnabled(self.loaded and self.on_detail)
        self.add_detail_btn.setEnabled(self.loaded and self.on_detail)
        self.back_btn.setEnabled(self.on_detail)
        if self.on_detail:
            self.item_hint.setText("Click + Add field, then a value on this page, or let Auto-detect find them.")
        elif has_link:
            self.item_hint.setText("Open one item to add values from its own page (phone, address, ...).")
        else:
            self.item_hint.setText("Optional. If the list doesn't show everything, click Mark item link on the "
                                   "List step first.")
        self.preview_details_btn.setVisible(any(b.page == "detail" for b in self.fields))
        self.preview_details_btn.setEnabled(on_list and has_link)
        selected = self._selected_field() is not None
        self.again_btn.setEnabled(self.loaded and selected)
        self.remove_btn.setEnabled(selected)
        self._fit_step_pages()
