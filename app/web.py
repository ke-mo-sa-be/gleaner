"""Builder browser page: injects picker.js in an isolated world and relays its results as a Qt signal."""

import json
import logging
import secrets
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript

from core import paths
from core.fetcher import UA_TOKEN

log = logging.getLogger(__name__)

PICKER_JS = (Path(__file__).with_name("picker.js")).read_text(encoding="utf-8")
WORLD = QWebEngineScript.ScriptWorldId.ApplicationWorld

_profile = None


def browser_profile():
    """Persistent profile so a user's manual sign-in on a site survives restarts (docs/SECURITY.md 1)."""
    global _profile
    if _profile is None:
        root = paths.data_home() / "browser"
        _profile = QWebEngineProfile("gleaner")
        _profile.setPersistentStoragePath(str(root / "storage"))
        _profile.setCachePath(str(root / "cache"))
        identify(_profile)
    return _profile


def identify(profile):
    """Add Gleaner's token to the browser's User-Agent (docs/SECURITY.md 3), keeping the rest unchanged."""
    agent = profile.httpUserAgent()
    if UA_TOKEN not in agent:
        profile.setHttpUserAgent(f"{agent} {UA_TOKEN}")


class PickerPage(QWebEnginePage):
    picked = Signal(dict)

    def __init__(self, profile=None, parent=None):
        super().__init__(profile or browser_profile(), parent)
        # Page scripts could console.log a fake result; they cannot know this token (isolated world).
        self.token = secrets.token_hex(8)
        self._prefix = "__GLEANER__" + self.token
        script = QWebEngineScript()
        script.setName("gleaner-picker")
        script.setSourceCode(PICKER_JS.replace("%TOKEN%", self.token))
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        script.setWorldId(WORLD)
        script.setRunsOnSubFrames(False)
        self.scripts().insert(script)

    def javaScriptConsoleMessage(self, level, message, line, source):
        if not message.startswith(self._prefix):
            return
        try:
            payload = json.loads(message[len(self._prefix):])
        except json.JSONDecodeError:
            log.warning("picker sent unreadable message")
            return
        self.picked.emit(payload)

    def call(self, js, callback=None):
        self.runJavaScript(js, WORLD, callback or (lambda _result: None))

    def start_pick(self, mode, **options):
        options = {k: v for k, v in options.items() if v is not None}
        self.call(f"window.__gleaner && window.__gleaner.start({json.dumps(mode)}, {json.dumps(options)})")

    def stop_pick(self):
        self.call("window.__gleaner && window.__gleaner.stop()")

    def show_list(self, item_selector, selector=None):
        args = json.dumps(item_selector) + ("" if selector is None else ", " + json.dumps(selector))
        self.call(f"window.__gleaner && window.__gleaner.show({args})")

    def show_one(self, selector):
        self.call(f"window.__gleaner && window.__gleaner.showOne({json.dumps(selector)})")

    def clear_highlights(self):
        self.call("window.__gleaner && window.__gleaner.clear()")

    def auto_detect(self, kind, callback):
        """callback(dict) with auto-detect results for a list page (kind="list") or item page ("detail")."""
        def parse(text):
            try:
                callback(json.loads(text) if text else {"type": "error", "message": "The page isn't ready yet."})
            except json.JSONDecodeError:
                callback({"type": "error", "message": "Auto-detect failed. Pick the fields by hand."})
        self.call(f"window.__gleaner ? JSON.stringify(window.__gleaner.autoDetect({json.dumps(kind)})) : ''", parse)

    def snapshot(self, callback):
        """callback(html) with the current DOM, minus the picker overlay."""
        self.call("window.__gleaner ? window.__gleaner.snapshot() : document.documentElement.outerHTML",
                  lambda html: callback(html or ""))
