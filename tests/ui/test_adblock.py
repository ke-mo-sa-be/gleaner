"""Ad remover in the built-in browser. Offscreen Qt against the local fixture site; no network."""

import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication, QUrl
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWidgets import QApplication

    from app import adblock
except ImportError:
    QApplication = None

from tests.integration.fixture_site import FixtureSite

_app = None


def setUpModule():
    global _app
    if QApplication is not None:
        _app = QApplication.instance() or QApplication([])


def wait_until(condition, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    raise AssertionError("timed out")


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class HostListTests(unittest.TestCase):
    def test_matching(self):
        hosts = adblock.load_hosts()
        self.assertIn("doubleclick.net", hosts)
        self.assertTrue(adblock.is_blocked("pagead2.googlesyndication.com", hosts))
        self.assertTrue(adblock.is_blocked("Securepubads.G.DoubleClick.net", hosts))
        self.assertFalse(adblock.is_blocked("notdoubleclick.net", hosts))
        self.assertFalse(adblock.is_blocked("doubleclick.net.example.com", hosts))
        self.assertFalse(adblock.is_blocked("www.drdata.in", hosts))
        # libraries pages need are not on the list
        for host in ("fonts.googleapis.com", "ajax.googleapis.com", "cdn.jsdelivr.net", "cdnjs.cloudflare.com"):
            self.assertFalse(adblock.is_blocked(host, hosts), host)


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.site = FixtureSite().__enter__()
        self.profile = QWebEngineProfile()
        self.blocker = adblock.install(self.profile, True, hosts=frozenset({"localhost"}))
        self.page = QWebEnginePage(self.profile)

    def tearDown(self):
        self.page.deleteLater()
        QCoreApplication.processEvents()
        self.site.__exit__(None, None, None)

    def load(self):
        done = []
        self.page.loadFinished.connect(done.append)
        self.page.load(QUrl(self.site.base + "/ads-page"))
        wait_until(lambda: done)
        self.page.loadFinished.disconnect()
        end = time.monotonic() + 0.5  # let late requests happen (or not)
        wait_until(lambda: time.monotonic() > end)

    def run_js(self, code):
        out = []
        self.page.runJavaScript(code, 0, out.append)
        wait_until(lambda: out)
        return out[0]

    def test_ads_blocked_and_hidden_page_kept(self):
        self.load()
        self.assertEqual(self.site.hits["/ad.png"] + self.site.hits["/ad.js"], 0)
        self.assertGreater(self.blocker.blocked, 0)
        self.assertEqual(self.run_js("document.getElementById('main').textContent"), "Real content")
        wait_until(lambda: self.run_js("getComputedStyle(document.querySelector('ins.adsbygoogle')).display")
                   == "none")

    def test_switched_off(self):
        adblock.install(self.profile, False)
        self.load()
        wait_until(lambda: self.site.hits["/ad.png"] > 0)
        self.assertNotEqual(self.run_js("getComputedStyle(document.querySelector('ins.adsbygoogle')).display"),
                            "none")


if __name__ == "__main__":
    unittest.main()
