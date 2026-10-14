"""Main window, settings, theme, guide and speed. Offscreen Qt, temporary data folder, no network."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWebEngineCore import QWebEngineProfile
    from PySide6.QtWidgets import QApplication

    from app import help_view, settings, style, web
    from app.main_window import GUIDE, SECTIONS, MainWindow
except ImportError:
    QApplication = None

from core import paths
from core.fetcher import MIN_DELAY_FLOOR, SPEEDS, speed_delays
from core.recipe import load_recipe
from core.store import Store

DRDATA = Path(__file__).resolve().parents[2] / "recipes" / "drdata.json"
_app = None


def setUpModule():
    global _app
    if QApplication is not None:
        _app = QApplication.instance() or QApplication([])
        web._profile = QWebEngineProfile()


class SpeedPresetTests(unittest.TestCase):
    def test_no_preset_below_floor(self):
        for name, (low, high) in SPEEDS.items():
            self.assertGreaterEqual(low, MIN_DELAY_FLOOR, name)
            self.assertGreaterEqual(high, low, name)
        self.assertEqual(speed_delays("nonsense"), SPEEDS["normal"])


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class ShellTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._old = os.environ.get("GLEANER_HOME")
        os.environ["GLEANER_HOME"] = self.tmp.name
        self.store = Store(paths.db_path())

    def tearDown(self):
        style.apply(_app, "light")
        self.store.close()
        if self._old is None:
            os.environ.pop("GLEANER_HOME", None)
        else:
            os.environ["GLEANER_HOME"] = self._old
        self.tmp.cleanup()

    def test_settings_round_trip_and_defaults(self):
        self.assertEqual((settings.theme(), settings.speed()), ("auto", "normal"))
        self.assertFalse(settings.guide_seen())
        settings.set_theme("dark")
        settings.set_speed("gentle")
        settings.set_guide_seen(True)
        settings.set_exports_dir(self.tmp.name)
        self.assertEqual((settings.theme(), settings.speed(), settings.guide_seen()), ("dark", "gentle", True))
        self.assertEqual(str(settings.exports_dir()), self.tmp.name)
        settings.set_speed("warp")  # unknown values fall back to safe defaults
        self.assertEqual(settings.speed(), "normal")
        self.assertTrue((paths.data_home() / "settings.ini").exists())

    def test_theme_switch(self):
        seen = []
        style.theme_changed.changed.connect(lambda: seen.append(style.is_dark()))
        style.apply(_app, "dark")
        self.assertEqual(style.color("BACKGROUND"), style.DARK["BACKGROUND"])
        style.apply(_app, "light")
        self.assertEqual(style.color("BACKGROUND"), style.LIGHT["BACKGROUND"])
        self.assertEqual(seen[-2:], [True, False])

    def test_guide_chapters(self):
        titles = [t for t, _b in help_view.load_chapters()]
        self.assertGreaterEqual(len(titles), 8)
        for key, prefix in help_view.KEYS.items():
            self.assertTrue(any(t.startswith(prefix) for t in titles), key)

    def wait(self, condition, timeout=10):
        import time
        end = time.monotonic() + timeout
        while time.monotonic() < end and not condition():
            QCoreApplication.processEvents()
            time.sleep(0.02)
        return condition()

    def test_master_list_and_share(self):
        w = MainWindow(self.store, check_updates=False)
        rid = self.store.save_recipe(load_recipe(DRDATA))
        self.store.save_record(rid, "https://www.drdata.in/a", {"Name": "Test Person", "Phone": "98450 00001",
                                                                "_start_page": "https://www.drdata.in/"})
        w.library.refresh()
        w.library.create_master([rid])
        self.assertTrue(self.wait(lambda: "Master list written" in w.library.banner.title.text()),
                        w.library.banner.title.text())
        self.assertTrue(any(p.name.startswith("Master_list_") for p in settings.exports_dir().iterdir()))

        w.library.table.selectRow(0)
        target = Path(self.tmp.name) / "shared.json"
        with mock.patch("app.library_view.QFileDialog.getSaveFileName", return_value=(str(target), "")):
            w.library._share()
        self.assertEqual(load_recipe(target).name, "drdata.in doctors")
        style.theme_changed.changed.disconnect(w.library.refresh)
        w.deleteLater()
        QCoreApplication.processEvents()

    def test_main_window_sections_and_help_routing(self):
        w = MainWindow(self.store, check_updates=False)
        self.assertEqual([w.nav.item(i).text() for i in range(w.nav.count())], list(SECTIONS))
        w.show_help("layers")
        self.assertEqual(w.nav.currentRow(), GUIDE)
        chapter = w.help_view.chapters[w.help_view.contents.currentRow()][0]
        self.assertTrue(chapter.startswith("Directories with many layers"))
        self.assertIn("Duplicate", w.help_view.page.toPlainText())

        settings.set_speed("faster")
        recipe_id = self.store.save_recipe(load_recipe(DRDATA))
        w.run_recipe(recipe_id)
        self.assertEqual(w.run_view.speed.currentData(), "faster")
        self.assertIn("3-5 seconds", w.run_view.speed_hint.text())

        w.settings_view.theme.setCurrentIndex(w.settings_view.theme.findData("dark"))
        self.assertEqual(settings.theme(), "dark")
        self.assertTrue(style.is_dark())
        style.theme_changed.changed.disconnect(w.library.refresh)  # store closes in tearDown
        w.deleteLater()
        QCoreApplication.processEvents()


if __name__ == "__main__":
    unittest.main()
