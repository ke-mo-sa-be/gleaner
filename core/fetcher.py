"""Polite HTTP fetcher.

One request at a time, a random pause between requests, robots.txt checked
before every new site, every page cached so it is never fetched twice, and a
hard stop the moment a site signals a block. There is deliberately no proxy,
IP rotation or CAPTCHA handling: a block ends the run for that source.
Pages of sites that build their content with JavaScript can be opened through a
renderer (Gleaner's own browser, supplied by the app); they go through exactly
the same pacing, robots, block and blank-page rules.
These rules are product requirements (docs/SECURITY.md section 3); this module
is the only place they are defined.
"""

import logging
import random
import threading
import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)

MIN_DELAY_FLOOR = 3.0  # seconds; user settings cannot go below this
UA_TOKEN = "Gleaner/0.8"  # in every request, also the built-in browser's, so site owners can identify the tool
USER_AGENT = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) {UA_TOKEN}"

# Pause between requests (min, max seconds) for the speed users can pick. "faster" sits on the floor;
# there is deliberately no preset below it (docs/SECURITY.md 3).
SPEEDS = {
    "gentle": (10.0, 20.0),
    "normal": (5.0, 10.0),
    "faster": (MIN_DELAY_FLOOR, 5.0),
}
DEFAULT_SPEED = "normal"


def speed_delays(name) -> tuple[float, float]:
    """Delays for a speed name; unknown names fall back to normal."""
    return SPEEDS.get(name, SPEEDS[DEFAULT_SPEED])

BLOCK_STATUS = {401, 403, 407, 429, 503}
# Markers only checked on short pages, so a normal page that merely embeds a
# reCAPTCHA widget on its contact form is not mistaken for a block page.
SHORT_PAGE_BLOCK_MARKERS = ("captcha", "access denied", "too many requests", "unusual traffic")
ANY_PAGE_BLOCK_MARKERS = ("cf-chl-", "error code: 1006", "error code: 1015", "attention required! | cloudflare")
MIN_PAGE_CHARS = 500


class RenderError(requests.RequestException):
    """The browser couldn't open the page (network problem or timeout); retried like a network error."""


RENDERED = "#gleaner-rendered"  # cache key suffix: a browser-built page is cached apart from the raw HTML


def cache_keys(url) -> tuple[str, str]:
    """Both page-cache keys a URL can be stored under (raw and browser-built)."""
    return url, url + RENDERED


class BlockedError(RuntimeError):
    """The site refused or challenged us. Stop this source; do not retry."""


class DisallowedError(RuntimeError):
    """robots.txt disallows this URL."""


class EmptyPageError(RuntimeError):
    """Site kept answering 200 with a blank body. Not cached, so a later run retries it."""


def looks_blocked(status: int, text: str) -> bool:
    if status in BLOCK_STATUS:
        return True
    lower = text.lower()
    if any(m in lower for m in ANY_PAGE_BLOCK_MARKERS):
        return True
    return len(text) < 20_000 and any(m in lower for m in SHORT_PAGE_BLOCK_MARKERS)


def _log_warning(msg):
    log.warning(msg)


# One clock for the whole process: a run and builder previews together still make at most one request
# per pause ("one request at a time per app instance", docs/SECURITY.md 3). The lock is held while
# sleeping on purpose, so waiting requests queue up behind each other.
_pace_lock = threading.Lock()
_last_request = 0.0


class Fetcher:
    """`store` needs get_page(url) -> str | None and save_page(url, status, html)."""

    def __init__(
        self,
        store,
        user_agent=USER_AGENT,
        min_delay=5.0,
        max_delay=10.0,
        timeout=30,
        max_retries=2,
        retry_wait=30.0,
        log=None,
        renderer=None,
        _min_delay_floor=MIN_DELAY_FLOOR,  # tests only; never exposed to users
    ):
        """renderer(url, wait_for) -> (status, html): opens a page in a browser (app/render.py)."""
        self.store = store
        self.renderer = renderer
        self.user_agent = user_agent
        self.min_delay = max(min_delay, _min_delay_floor)
        self.max_delay = max(max_delay, self.min_delay)
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_wait = retry_wait
        self.log = log or _log_warning
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Language": "en-IN,en;q=0.9"})
        self._robots = {}
        self.requests_made = 0

    def _wait(self):
        global _last_request
        pause = random.uniform(self.min_delay, self.max_delay)
        with _pace_lock:
            remaining = _last_request + pause - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            _last_request = time.monotonic()

    def _robots_for(self, url):
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            self._wait()
            resp = self.session.get(base + "/robots.txt", timeout=self.timeout)
            self.requests_made += 1
            if resp.status_code in BLOCK_STATUS:
                raise BlockedError(f"robots.txt returned {resp.status_code} on {base}")
            if resp.status_code == 200:
                parser.parse(resp.text.splitlines())
            else:
                parser.allow_all = True
            self._robots[base] = parser
        return self._robots[base]

    def allowed(self, url) -> bool:
        """robots.txt check without fetching the page itself."""
        return self._robots_for(url).can_fetch(self.user_agent, url)

    def _download(self, url, render, wait_for) -> tuple[int, str]:
        if not render:
            resp = self.session.get(url, timeout=self.timeout)
            return resp.status_code, resp.text
        if self.renderer is None:
            raise RuntimeError("this recipe opens pages in Gleaner's browser; run it from the app")
        return self.renderer(url, wait_for)

    def get(self, url, refresh=False, render=False, wait_for=None):
        """Return page HTML, from cache when possible.

        render: open the page in the browser (sites that build pages with JavaScript); wait_for is a CSS
        selector the page should show before it counts as loaded.
        Raises BlockedError, DisallowedError, EmptyPageError or requests.RequestException.
        """
        key = url + RENDERED if render else url
        if not refresh:
            cached = self.store.get_page(key)
            if cached is not None:
                return cached

        if not self.allowed(url):
            raise DisallowedError(url)

        for attempt in range(self.max_retries + 1):
            wait = self.retry_wait * (attempt + 1)
            self._wait()
            try:
                status, text = self._download(url, render, wait_for)
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    raise
                self.log(f"network error ({exc.__class__.__name__}), retrying in {wait:.0f}s")
                time.sleep(wait)
                continue

            self.requests_made += 1
            if looks_blocked(status, text):
                raise BlockedError(f"HTTP {status} block signal at {url}")
            if status >= 500 and attempt < self.max_retries:
                self.log(f"server error {status}, retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
            if status >= 400:
                raise requests.HTTPError(f"HTTP {status} for {url}")
            if len(text.strip()) < MIN_PAGE_CHARS:
                if attempt == self.max_retries:
                    raise EmptyPageError(url)
                self.log(f"blank page, retrying in {wait:.0f}s")
                time.sleep(wait)
                continue

            self.store.save_page(key, status, text)
            return text
