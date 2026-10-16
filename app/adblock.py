"""Ad remover for Gleaner's built-in browser (Recipe builder and browser runs).

Requests to known ad and tracking networks (adblock_hosts.txt) are dropped before they load, and common
empty ad boxes are hidden. The page the user opens is never blocked, and the site's own HTML is left as
it is, so what the builder shows still matches what a run reads. Settings > Block ads turns it off.
"""

import json
import logging
from pathlib import Path

from PySide6.QtWebEngineCore import QWebEngineScript, QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor

log = logging.getLogger(__name__)

HOSTS_FILE = Path(__file__).with_name("adblock_hosts.txt")

# Ad slots that stay as empty boxes once their ads are blocked. Hidden only; nothing is removed.
HIDE_CSS = ", ".join([
    "ins.adsbygoogle", ".adsbygoogle", "[data-ad-slot]", "[data-ad-client]", "[data-google-query-id]",
    "div[id^='div-gpt-ad']", "div[id^='google_ads_iframe']", "iframe[id^='google_ads_iframe']",
    "iframe[src*='doubleclick.net']", "iframe[src*='googlesyndication.com']", "iframe[src*='amazon-adsystem.com']",
    "div[id^='taboola-']", ".trc_related_container", ".OUTBRAIN", "div[data-widget-id^='outbrain']",
    ".mgid-widget", "#google_vignette",
]) + " { display: none !important; }"

HIDE_JS = """(() => {
  if (document.getElementById('gleaner-adhide')) return;
  const style = document.createElement('style');
  style.id = 'gleaner-adhide';
  style.textContent = %s;
  (document.head || document.documentElement).appendChild(style);
})();""" % json.dumps(HIDE_CSS)


def load_hosts(path=HOSTS_FILE) -> frozenset:
    hosts = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip().lower()
        if line:
            hosts.add(line)
    return frozenset(hosts)


def is_blocked(host: str, hosts) -> bool:
    """True when host or one of its parent domains is on the list (ads.example.com matches example.com)."""
    parts = (host or "").lower().rstrip(".").split(".")
    return any(".".join(parts[i:]) in hosts for i in range(len(parts) - 1)) or (host or "").lower() in hosts


class AdBlocker(QWebEngineUrlRequestInterceptor):
    """Runs on the browser's network thread: keep it to a set lookup."""

    def __init__(self, hosts=None, parent=None):
        super().__init__(parent)
        self.hosts = hosts if hosts is not None else load_hosts()
        self.enabled = True
        self.blocked = 0

    def interceptRequest(self, info):
        if not self.enabled or info.resourceType() == QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMainFrame:
            return  # never block the page itself
        if is_blocked(info.requestUrl().host(), self.hosts):
            info.block(True)
            self.blocked += 1


_blockers = {}


def install(profile, enabled=True, hosts=None):
    """Attach the ad remover to a browser profile (once) and switch it on or off."""
    key = id(profile)
    if key not in _blockers:
        blocker = AdBlocker(hosts, parent=profile)
        profile.setUrlRequestInterceptor(blocker)
        _blockers[key] = blocker
    blocker = _blockers[key]
    blocker.enabled = enabled
    scripts = profile.scripts()
    for old in scripts.find("gleaner-adhide"):
        scripts.remove(old)
    if enabled:
        script = QWebEngineScript()
        script.setName("gleaner-adhide")
        script.setSourceCode(HIDE_JS)
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
        script.setRunsOnSubFrames(False)
        scripts.insert(script)
    return blocker
