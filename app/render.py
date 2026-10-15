"""Open pages in Gleaner's own browser during runs, for sites that build their lists with JavaScript.

core.fetcher calls the renderer from a run thread; the browser lives on the UI thread. Each call opens
one page in a hidden browser tab (pictures off), waits until the content has settled, and returns the
page as the browser built it. Pacing, robots, block and blank-page rules stay in core/fetcher.py.
"""

import json
import logging
import threading
import time

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtWebEngineCore import QWebEngineLoadingInfo, QWebEnginePage, QWebEngineSettings

from app.web import WORLD, browser_profile
from core.fetcher import RenderError

log = logging.getLogger(__name__)

LOAD_TIMEOUT = 45.0  # seconds for the page itself to load
SETTLE_LIMIT = 20.0  # seconds to wait for scripts to finish building the content
POLL_MS = 500
STABLE_POLLS = 3  # content unchanged for this many polls in a row counts as finished

PROBE = """(() => {
  const body = document.body;
  const sel = %s;
  let found = -1;
  if (sel) { try { found = document.querySelectorAll(sel).length; } catch (e) { found = 0; } }
  return JSON.stringify([body ? body.innerText.length : 0, found]);
})()"""


class _Job:
    def __init__(self, url, wait_for):
        self.url = url
        self.wait_for = wait_for
        self.status = 0
        self.html = None
        self.error = None
        self.cancelled = False
        self.done = threading.Event()


class PageRenderer(QObject):
    """Create on the UI thread; call from any other thread: renderer(url, wait_for) -> (status, html)."""

    _requested = Signal(object)

    def __init__(self, parent=None, profile=None):
        super().__init__(parent)
        self._profile = profile
        self._requested.connect(self._open, Qt.ConnectionType.QueuedConnection)

    def __call__(self, url, wait_for=None):
        if threading.current_thread() is threading.main_thread():
            raise RuntimeError("PageRenderer must be called from a background thread")
        job = _Job(url, wait_for)
        self._requested.emit(job)
        if not job.done.wait(LOAD_TIMEOUT + SETTLE_LIMIT + 15):
            job.cancelled = True
            raise RenderError(f"the browser did not finish opening {url}")
        if job.error:
            raise RenderError(job.error)
        return job.status, job.html

    # ---- UI thread ---------------------------------------------------------------------------

    def _open(self, job):
        page = QWebEnginePage(self._profile or browser_profile(), self)
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, False)  # less load on the site
        page.setAudioMuted(True)
        state = {"status": 200, "started": time.monotonic(), "last": None, "same": 0, "loaded": False,
                 "finished": False}
        timer = QTimer(page)

        def finish(html=None, error=None):
            if state["finished"]:
                return
            state["finished"] = True
            timer.stop()
            job.status, job.html, job.error = state["status"], html, error
            job.done.set()
            page.deleteLater()

        def loading(info):
            if info.status() == QWebEngineLoadingInfo.LoadStatus.LoadFailedStatus:
                if info.errorDomain() == QWebEngineLoadingInfo.ErrorDomain.HttpStatusCodeDomain:
                    state["status"] = info.errorCode()  # the page text is still checked for block signals
                    state["loaded"] = True
                    state["started"] = time.monotonic()
                    timer.start(POLL_MS)
                elif not state["loaded"]:
                    finish(error=f"couldn't open the page ({info.errorString() or info.errorCode()})")
            elif info.status() == QWebEngineLoadingInfo.LoadStatus.LoadSucceededStatus:
                state["loaded"] = True
                state["started"] = time.monotonic()
                timer.start(POLL_MS)

        def probe():
            if job.cancelled:
                finish(error="cancelled")
                return
            page.runJavaScript(PROBE % json.dumps(job.wait_for or ""), WORLD, settled)

        def settled(result):
            if state["finished"]:
                return
            try:
                length, found = json.loads(result) if isinstance(result, str) else (0, -1)
            except ValueError:
                length, found = 0, -1
            state["same"] = state["same"] + 1 if (length, found) == state["last"] else 0
            state["last"] = (length, found)
            ready = length > 0 and state["same"] >= (1 if found > 0 else STABLE_POLLS)
            if ready or time.monotonic() - state["started"] > SETTLE_LIMIT:
                timer.stop()
                page.toHtml(lambda html: finish(html=html))

        def load_timeout():
            if not state["loaded"]:
                finish(error="the page took too long to load")

        timer.timeout.connect(probe)
        page.loadingChanged.connect(loading)
        QTimer.singleShot(int(LOAD_TIMEOUT * 1000), page, load_timeout)
        page.load(QUrl(job.url))


_renderer = None


def renderer():
    """The app's shared renderer. First call must be on the UI thread (the main window does it)."""
    global _renderer
    if _renderer is None:
        _renderer = PageRenderer()
    return _renderer
