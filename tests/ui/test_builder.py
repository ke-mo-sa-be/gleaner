"""End-to-end Builder test: point-and-click a recipe on the local fixture site, save it, run it.
Offscreen Qt; synthetic site on 127.0.0.1 only."""

import json
import os
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication

    from PySide6.QtWebEngineCore import QWebEngineProfile

    from app import builder_view, web
    from app.web import WORLD
except ImportError:
    QApplication = None

from core import paths
from core.fetcher import Fetcher
from core.runner import run_recipe
from core.store import Store
from tests.integration.fixture_site import FixtureSite

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
        self.builder.deleteLater()
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

        b._add_detail_field()
        self.click("table.info tr:nth-of-type(2) td:nth-of-type(2)")
        wait_until(lambda: len(b.fields) == 3)
        phone = b.fields[2].field
        self.assertEqual((phone.name, phone.label, phone.label_scope, phone.type),
                         ("Phone Number", "Phone Number", "table.info tr", "phone"))

        b._back_to_list()
        wait_until(lambda: b.loaded and not b.on_detail)
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

    def test_local_address_rejected_without_test_flag(self):
        b = builder_view.BuilderView(self.store)
        b.url_edit.setText(self.site.base + "/list")
        b.open_url()
        self.assertIn("local network", b.instruction.text())
        b.deleteLater()


if __name__ == "__main__":
    unittest.main()
