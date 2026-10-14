"""Picker tests in an offscreen QtWebEngine page: selectors the browser builds must extract the same
values in core.extract (BeautifulSoup). Synthetic pages only; no network."""

import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEventLoop, QTimer, QUrl
    from PySide6.QtWebEngineCore import QWebEngineProfile
    from PySide6.QtWidgets import QApplication

    from app.web import WORLD, PickerPage
except ImportError:  # PySide6 not installed: UI tests skipped
    QApplication = None

from core.extract import extract_detail, extract_list, next_page_url
from core.recipe import Detail, Field, Pagination, Recipe

TABLE = """<html><body><div class="container"><section id="no-more-tables">
<table class="table"><thead><tr><th>Name</th><th>City</th><th>Details</th></tr></thead><tbody>
<tr><td data-title="Name">DR. A</td><td data-title="City">PUNE</td>
    <td data-title="Details"><a href="/dr-a"><button class="btn">Connect</button></a></td></tr>
<tr><td data-title="Name">DR. B</td><td data-title="City">GOA</td>
    <td data-title="Details"><a href="/dr-b"><button class="btn">Connect</button></a></td></tr>
<tr><td data-title="Name">DR. C</td><td data-title="City"></td>
    <td data-title="Details"><a href="/dr-c"><button class="btn">Connect</button></a></td></tr>
</tbody></table></section>
<div class="pager"><a class="pnavi" href="list?page=2">2</a><a class="pnavi" href="list?page=3">3</a></div>
<h1>Doctors</h1></div></body></html>"""

CARDS = """<html><body><div id="results">
<div class="card"><h3 class="title">Alpha Clinic</h3><p class="phone">98450 00001</p></div>
<div class="card featured"><h3 class="title">Beta Clinic</h3><p class="phone">98450 00002</p></div>
<div class="card"><h3 class="title">Gamma Clinic</h3></div>
</div><ul><li><span>x1</span><span>y1</span></li><li><span>x2</span><span>y2</span></li></ul>
<nav><a href="/cards?p=1">Prev</a><a href="/cards?p=3">Next</a></nav></body></html>"""

DETAIL = """<html><body><div id="profile"><table><tbody>
<tr><td><strong>Name</strong></td><td>DR. A</td></tr>
<tr><td><strong>Phone Number</strong></td><td>98450 00000</td></tr>
<tr><td><strong>Address</strong></td><td>1 Main Rd, Pune 411001</td></tr>
</tbody></table><dl class="extra"><dt>Email</dt><dd>a@b.in</dd></dl>
<p class="note"><span>Visiting hours</span></p></div></body></html>"""

_app = None


def setUpModule():
    global _app
    if QApplication is not None:
        _app = QApplication.instance() or QApplication([])


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class PickerTests(unittest.TestCase):
    def setUp(self):
        self.profile = QWebEngineProfile()  # off-the-record
        self.page = PickerPage(profile=self.profile)
        self.messages = []
        self.page.picked.connect(self.messages.append)

    def tearDown(self):
        self.page.deleteLater()

    def _wait(self, start):
        loop = QEventLoop()
        box = {}

        def done(value=None):
            box["value"] = value
            loop.quit()

        start(done)
        QTimer.singleShot(15000, loop.quit)
        loop.exec()
        return box.get("value")

    def load(self, html, url):
        def start(done):
            self.page.loadFinished.connect(done)
            self.page.setHtml(html, QUrl(url))
        self._wait(start)
        self.page.loadFinished.disconnect()
        self.html = html
        self.url = url

    def js(self, code, world=WORLD):
        return self._wait(lambda done: self.page.runJavaScript(code, world, done))

    def pick(self, mode, css, **options):
        # runJavaScript cannot return JS objects to PySide; send JSON text.
        return json.loads(self.js(
            f"window.__gleaner.start({json.dumps(mode)}, {json.dumps(options)});"
            f"JSON.stringify(window.__gleaner.handle(document.querySelector({json.dumps(css)})))"))

    def snapshot(self):
        return self._wait(self.page.snapshot)

    def list_recipe(self, item_selector, *fields):
        return Recipe(name="t", start_url=self.url, item_selector=item_selector, list_fields=list(fields))

    # -- list pages ----------------------------------------------------------------------------

    def test_table_field_and_refine(self):
        self.load(TABLE, "https://example.com/list")
        res = self.pick("list", "tr:nth-of-type(1) td[data-title=City]")
        self.assertEqual(res["type"], "list")
        self.assertEqual(res["itemSelector"], "#no-more-tables table.table tr")
        self.assertEqual(res["selector"], ':scope td[data-title="City"]')
        self.assertEqual(res["count"], 3)
        self.assertEqual(res["hint"], "City")
        name = self.pick("list", "tr:nth-of-type(2) td[data-title=Name]", itemSelector=res["itemSelector"])
        recipe = self.list_recipe(res["itemSelector"], Field("Name", name["selector"]), Field("City", res["selector"]))
        expected = [{"Name": "DR. A", "City": "PUNE"}, {"Name": "DR. B", "City": "GOA"}, {"Name": "DR. C", "City": None}]
        # header row yields nothing and is dropped; raw HTML and browser DOM agree
        self.assertEqual(extract_list(self.html, recipe, self.url), expected)
        self.assertEqual(extract_list(self.snapshot(), recipe, self.url), expected)
        self.assertEqual(self.messages[-1]["type"], "list")  # relayed over the console bridge

    def test_detail_link_inside_button(self):
        self.load(TABLE, "https://example.com/list")
        res = self.pick("link", "tr:nth-of-type(2) button")
        self.assertEqual(res["type"], "link")
        self.assertEqual(res["href"], "https://example.com/dr-b")
        recipe = self.list_recipe(res["itemSelector"], Field("Link", res["selector"], attr="href", type="link"))
        self.assertEqual([r["Link"] for r in extract_list(self.html, recipe, self.url)],
                         ["https://example.com/dr-a", "https://example.com/dr-b", "https://example.com/dr-c"])

    def test_page_number_link_becomes_page_param(self):
        self.load(TABLE, "https://example.com/list")
        res = self.pick("next", "a.pnavi")
        self.assertEqual(res["pagination"], {"type": "page_param", "param": "page", "start": 1})

    def test_next_link_by_text(self):
        self.load(CARDS, "https://example.com/cards?p=2")
        res = self.pick("next", "nav a:nth-of-type(2)")
        p = res["pagination"]
        self.assertEqual(p["type"], "page_param")  # p=3 is current+1
        self.load(CARDS, "https://example.com/cards")
        p = self.pick("next", "nav a:nth-of-type(2)")["pagination"]
        self.assertEqual((p["type"], p["text"]), ("next_link", "Next"))
        recipe = self.list_recipe("#results div.card", Field("T", ":scope"))
        recipe.pagination = Pagination(type="next_link", selector=p["selector"], text=p["text"])
        self.assertEqual(next_page_url(self.html, recipe, self.url, 1), "https://example.com/cards?p=3")

    def test_cards_with_missing_field(self):
        self.load(CARDS, "https://example.com/cards")
        res = self.pick("list", "div.featured p.phone")
        self.assertEqual(res["itemSelector"], "#results div.card")
        self.assertEqual(res["selector"], ":scope p.phone")
        recipe = self.list_recipe(res["itemSelector"], Field("Name", ":scope h3.title"), Field("Phone", res["selector"]))
        self.assertEqual([r["Phone"] for r in extract_list(self.html, recipe, self.url)],
                         ["98450 00001", "98450 00002", None])

    def test_positional_fields_without_classes(self):
        self.load(CARDS, "https://example.com/cards")
        res = self.pick("list", "li:nth-of-type(1) span:nth-of-type(2)")
        self.assertEqual((res["itemSelector"], res["selector"]), ("ul li", ":scope span:nth-of-type(2)"))
        recipe = self.list_recipe(res["itemSelector"], Field("Y", res["selector"]))
        self.assertEqual([r["Y"] for r in extract_list(self.html, recipe, self.url)], ["y1", "y2"])

    def test_single_element_is_not_a_list(self):
        self.load(TABLE, "https://example.com/list")
        res = self.pick("list", "h1")
        self.assertEqual(res["type"], "error")
        self.assertIn("single item", res["message"])

    # -- detail pages --------------------------------------------------------------------------

    def test_detail_label_rows_and_dt_dd(self):
        self.load(DETAIL, "https://example.com/dr-a")
        phone = self.pick("detail", "tr:nth-of-type(2) td:nth-of-type(2)")
        self.assertEqual((phone["label"], phone["label_scope"]), ("Phone Number", "#profile table tr"))
        email = self.pick("detail", "dd")
        self.assertEqual((email["label"], email["label_scope"]), ("Email", "#profile dl.extra dt"))
        note = self.pick("detail", "p.note span")
        self.assertNotIn("label", note)
        recipe = Recipe(name="t", start_url=self.url, item_selector="x", list_fields=[Field("L", "a")],
                        detail=Detail("L", [
                            Field("Phone", label=phone["label"], label_scope=phone["label_scope"]),
                            Field("Email", label=email["label"], label_scope=email["label_scope"]),
                            Field("Note", note["selector"]),
                        ]))
        expected = {"Phone": "98450 00000", "Email": "a@b.in", "Note": "Visiting hours"}
        self.assertEqual(extract_detail(self.html, recipe, self.url), expected)
        self.assertEqual(extract_detail(self.snapshot(), recipe, self.url), expected)

    # -- isolation -----------------------------------------------------------------------------

    def test_page_scripts_cannot_see_picker(self):
        self.load(TABLE, "https://example.com/list")
        self.assertEqual(self.js("typeof window.__gleaner", world=0), "undefined")
        self.assertEqual(self.js("typeof window.__gleaner"), "object")
        self.assertNotIn("__gleaner_layer", self.snapshot())


if __name__ == "__main__":
    unittest.main()
