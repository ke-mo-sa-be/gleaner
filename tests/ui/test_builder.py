"""End-to-end Builder test: point-and-click a recipe on the local fixture site, save it, run it.
Offscreen Qt; synthetic site on 127.0.0.1 only."""

import json
import os
import tempfile
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    from PySide6.QtWebEngineCore import QWebEngineProfile

    from app import builder_view, render, web
    from app.web import WORLD
except ImportError:
    QApplication = None

from core import paths
from core.fetcher import BlockedError, Fetcher
from core.runner import run_recipe
from core.store import Store
from tests.integration.fixture_site import FixtureSite


def dispose(widget):
    """Destroy a widget now. deleteLater() alone would destroy it during a later test, while its browser
    page may still be sending signals."""
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()

_app = None


def setUpModule():
    global _app
    if QApplication is not None:
        _app = QApplication.instance() or QApplication([])
        web._profile = QWebEngineProfile()  # off-the-record: nothing written to disk


def wait_until(condition, timeout=20.0, builder=None):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    state = ""
    if builder is not None:
        state = (f" (loaded={builder.loaded}, on_detail={builder.on_detail}, "
                 f"url={builder.page.url().toString()!r}, instruction={builder.instruction.text()!r})")
    raise AssertionError("timed out waiting for the builder" + state)


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class BuilderFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_home = os.environ.get("GLEANER_HOME")
        os.environ["GLEANER_HOME"] = self.tmp.name
        self.site = FixtureSite().__enter__()
        builder_view.FETCHER_OPTIONS.update(min_delay=0, max_delay=0, retry_wait=0, _min_delay_floor=0)
        self.store = Store(paths.db_path(), allow_local_urls=True)
        self.builder = builder_view.BuilderView(self.store, allow_local=True)

    def tearDown(self):
        builder_view.FETCHER_OPTIONS.clear()
        dispose(self.builder)
        QCoreApplication.processEvents()
        self.store.close()
        self.site.__exit__(None, None, None)
        if self._old_home is None:
            os.environ.pop("GLEANER_HOME", None)
        else:
            os.environ["GLEANER_HOME"] = self._old_home
        self.tmp.cleanup()

    def click(self, css):
        """What a user's click in pick mode does: hand the element to the picker."""
        self.builder.page.runJavaScript(
            f"window.__gleaner.handle(document.querySelector({json.dumps(css)}))", WORLD, lambda _r: None)

    def test_point_and_click_recipe_then_run(self):
        b = self.builder
        b.url_edit.setText(self.site.base + "/list")
        b.open_url()
        wait_until(lambda: b.loaded and not b.on_detail, builder=b)

        b._add_list_field()
        self.click("li.item b.name")
        wait_until(lambda: len(b.fields) == 1)
        self.assertEqual(b.item_selector, "#results li.item")
        b.fields[0].field.name = "Doctor"
        wait_until(lambda: b.preview_table.rowCount() == 3)

        b._mark_link()
        self.click("li.item a.more")
        wait_until(lambda: b.on_detail and b.loaded)
        self.assertTrue(b.fields[1].is_link)
        self.assertEqual(b.tabs.currentIndex(), builder_view.ITEM)  # follows the page to the item step
        self.assertFalse(b.open_detail_btn.isVisibleTo(b))
        self.assertTrue(b.add_detail_btn.isVisibleTo(b))

        b._add_detail_field()
        self.click("table.info tr:nth-of-type(2) td:nth-of-type(2)")
        wait_until(lambda: len(b.fields) == 3)
        phone = b.fields[2].field
        self.assertEqual((phone.name, phone.label, phone.label_scope, phone.type),
                         ("Phone Number", "Phone Number", "table.info tr", "phone"))

        self.assertEqual(b.fields_table.rowCount(), 1)  # only the item page's columns on that step
        b._back_to_list()
        wait_until(lambda: b.loaded and not b.on_detail)
        self.assertEqual(b.tabs.currentIndex(), builder_view.LIST)
        self.assertEqual(b.fields_table.rowCount(), 2)
        self.assertTrue(b.tabs.tabText(builder_view.LIST).startswith("✓"))
        b._mark_next()
        self.click("a.next")
        wait_until(lambda: b.pagination.type != "none")
        self.assertEqual((b.pagination.type, b.pagination.param), ("page_param", "page"))

        saved = []
        b.saved.connect(saved.append)
        b.name_edit.setText("Fixture doctors")
        b._save()
        wait_until(lambda: saved)

        recipe = self.store.get_recipe(saved[0])
        self.assertEqual(recipe.start_url, self.site.base + "/list")
        self.assertEqual(recipe.detail.link_field, "Item link")
        self.assertEqual(recipe.dedup_keys, ["Doctor", "Phone Number"])

        fetcher = Fetcher(self.store, min_delay=0, max_delay=0, retry_wait=0, _min_delay_floor=0)
        result = run_recipe(self.store, saved[0], fetcher)
        self.assertEqual((result.status, result.records), ("done", 6))
        first = self.store.records(saved[0])[0]["data"]
        self.assertEqual((first["Doctor"], first["Phone Number"]), ("DR. ALPHA", "98450 00001"))

    def test_auto_detect_and_start_pages(self):
        b = self.builder
        b.url_edit.setText(self.site.base + "/list")
        b.open_url()
        wait_until(lambda: b.loaded and not b.on_detail, builder=b)

        b._auto_detect()
        wait_until(lambda: any(x.is_link for x in b.fields), builder=b)
        self.assertEqual(b.item_selector, "#results li.item")
        self.assertEqual([x.field.name for x in b.fields], ["Name", "Item link"])  # constant "View" left out
        self.assertEqual((b.pagination.type, b.pagination.param), ("page_param", "page"))

        b._open_sample_detail()
        wait_until(lambda: b.on_detail and b.loaded, builder=b)
        b._auto_detect()
        wait_until(lambda: any(x.page == "detail" for x in b.fields), builder=b)
        labels = [x.field.label for x in b.fields if x.page == "detail"]
        self.assertEqual(labels, ["Name", "Phone Number", "Address :"])
        phone = next(x.field for x in b.fields if x.field.label == "Phone Number")
        self.assertEqual(phone.type, "phone")

        b._back_to_list()
        wait_until(lambda: b.loaded and not b.on_detail, builder=b)
        b._add_start_page()
        self.assertEqual(b.start_urls, [self.site.base + "/list"])
        with mock.patch.object(builder_view.QInputDialog, "getMultiLineText",
                               return_value=(f"{self.site.base}/list-b\nnot an address\n{self.site.base}/list", True)):
            b._paste_start_pages()
        self.assertEqual(b.start_urls, [self.site.base + "/list", self.site.base + "/list-b"])
        self.assertIn("1 lines were not usable", b.instruction.text())

        saved = []
        b.saved.connect(saved.append)
        b.name_edit.setText("Fixture auto")
        b._save()
        wait_until(lambda: saved, builder=b)
        recipe = self.store.get_recipe(saved[0])
        self.assertEqual(recipe.start_pages(), [self.site.base + "/list", self.site.base + "/list-b"])
        fetcher = Fetcher(self.store, min_delay=0, max_delay=0, retry_wait=0, _min_delay_floor=0)
        result = run_recipe(self.store, saved[0], fetcher)
        self.assertEqual((result.status, result.records), ("done", 8))

    def test_heading_list_with_phone_country(self):
        b = self.builder
        b.url_edit.setText(self.site.base + "/sections")
        b.open_url()
        wait_until(lambda: b.loaded and not b.on_detail, builder=b)

        b._auto_detect()
        wait_until(lambda: any(x.page == "list" for x in b.fields), builder=b)
        self.assertEqual(b.item_mode, "sections")
        self.assertEqual(b.list_type.currentData(), "sections")
        self.assertTrue(b.item_selector.endswith("div.entry-content h3.wp-block-heading"))
        names = [x.field.name for x in b.fields]
        self.assertEqual(names[:2], ["Name", "Address"])
        email = next(x.field for x in b.fields if x.field.label == "Email")
        self.assertEqual(email.type, "email")
        wait_until(lambda: b.preview_table.rowCount() == 3, builder=b)

        b.country.setCurrentIndex(b.country.findData("234"))
        b._country_chosen(0)
        self.assertEqual(b.phone_country, "234")

        saved = []
        b.saved.connect(saved.append)
        b.name_edit.setText("Fixture suppliers")
        b._save()
        wait_until(lambda: saved, builder=b)
        recipe = self.store.get_recipe(saved[0])
        self.assertEqual((recipe.item_mode, recipe.phone_country), ("sections", "234"))
        fetcher = Fetcher(self.store, min_delay=0, max_delay=0, retry_wait=0, _min_delay_floor=0)
        result = run_recipe(self.store, saved[0], fetcher)
        self.assertEqual((result.status, result.records), ("done", 3))
        rows = [r["data"] for r in self.store.records(saved[0])]
        self.assertEqual([r["Name"] for r in rows], ["Alpha Medical Ltd", "Beta Labs", "Gamma Devices"])
        self.assertEqual(rows[1]["Email"], "info@beta.test")

        # reopening keeps the list type and country
        b.load_recipe(saved[0])
        wait_until(lambda: b.loaded and not b.on_detail, builder=b)  # let the robots check finish
        self.assertEqual((b.list_type.currentData(), b.country.currentData()), ("sections", "234"))

    def test_back_and_forward(self):
        b = self.builder
        b.url_edit.setText(self.site.base + "/list")
        b.open_url()
        wait_until(lambda: b.loaded and not b.on_detail, builder=b)
        self.assertFalse(b.nav_back_btn.isEnabled())
        b._mark_link()
        self.click("li.item a.more")
        wait_until(lambda: b.on_detail and b.loaded, builder=b)
        self.assertTrue(b.nav_back_btn.isEnabled())

        b._nav_back()
        wait_until(lambda: b.loaded and not b.on_detail, builder=b)
        self.assertEqual(b.page.url().toString(), self.site.base + "/list")
        self.assertTrue(b.add_list_btn.isEnabled())
        self.assertTrue(b.nav_forward_btn.isEnabled())

        b._nav_forward()
        wait_until(lambda: b.loaded and b.on_detail, builder=b)
        self.assertTrue(b.add_detail_btn.isEnabled())

        b._reload()
        wait_until(lambda: b.loaded, builder=b)
        self.assertTrue(b.on_detail)

    def test_javascript_list_is_saved_and_run_in_the_browser(self):
        b = self.builder
        b.url_edit.setText(self.site.base + "/js-list")
        b.open_url()
        wait_until(lambda: b.loaded and not b.on_detail, builder=b)
        built = []  # the page's script adds the list after 300 ms
        poll = lambda: b.page.runJavaScript("document.querySelectorAll('li.item').length", 0, built.append)
        wait_until(lambda: (poll(), built and built[-1] == 3)[1], builder=b)
        b._add_list_field()
        self.click("li.item b.name")
        wait_until(lambda: len(b.fields) == 1, builder=b)
        b._mark_link()
        self.click("li.item a.more")
        wait_until(lambda: b.on_detail and b.loaded, builder=b)
        b._add_detail_field()
        self.click("table.info tr:nth-of-type(2) td:nth-of-type(2)")
        wait_until(lambda: len(b.fields) == 3, builder=b)
        b._back_to_list()
        wait_until(lambda: b.loaded and not b.on_detail and b.preview_table.rowCount() == 3, builder=b)

        saved = []
        b.saved.connect(saved.append)
        b.name_edit.setText("Fixture JavaScript list")
        b._save()
        wait_until(lambda: saved, builder=b)
        self.assertIn("builds its list with JavaScript", b.instruction.text())
        recipe = self.store.get_recipe(saved[0])
        self.assertTrue(recipe.render_js)

        # A run opens each page in the browser (from the run thread) and finds the list the script built.
        results = []

        def run():  # like the Run screen: the run thread has its own Store
            store = Store(paths.db_path(), allow_local_urls=True)
            try:
                fetcher = Fetcher(store, min_delay=0, max_delay=0, retry_wait=0, _min_delay_floor=0,
                                  renderer=render.renderer())
                results.append(run_recipe(store, saved[0], fetcher))
            finally:
                store.close()

        thread = threading.Thread(target=run)
        thread.start()
        wait_until(lambda: not thread.is_alive(), timeout=60, builder=b)
        self.assertEqual((results[0].status, results[0].records), ("done", 3))
        rows = [r["data"] for r in self.store.records(saved[0])]
        name = recipe.list_fields[0].name
        self.assertEqual([r[name] for r in rows], ["DR. ALPHA", "DR. BETA", "DR. GAMMA"])
        self.assertEqual(rows[1]["Phone Number"], "98450 00002")

    def test_renderer_reports_http_status(self):
        out = []
        thread = threading.Thread(target=lambda: out.append(render.renderer()(self.site.base + "/limited/1")))
        thread.start()
        wait_until(lambda: not thread.is_alive(), timeout=60)
        status, html = out[0]
        self.assertEqual(status, 429)
        fetcher = Fetcher(self.store, min_delay=0, max_delay=0, retry_wait=0, _min_delay_floor=0,
                          renderer=lambda url, wait_for: (status, html))
        with self.assertRaises(BlockedError):
            fetcher.get(self.site.base + "/limited/1", render=True)

    def test_local_address_rejected_without_test_flag(self):
        b = builder_view.BuilderView(self.store)
        b.url_edit.setText(self.site.base + "/list")
        b.open_url()
        self.assertIn("local network", b.instruction.text())
        dispose(b)


if __name__ == "__main__":
    unittest.main()
