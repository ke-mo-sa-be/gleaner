"""Crawl loop driven by a recipe. UI-free: reports through a callback, controlled through RunControl."""

import logging
import threading
from dataclasses import dataclass

import requests

from core.extract import extract_detail, extract_list, next_page_url
from core.fetcher import BlockedError, DisallowedError, EmptyPageError
from core.recipe import Recipe

log = logging.getLogger(__name__)

MAX_CONSECUTIVE_EMPTY = 3


class StopRequested(Exception):
    pass


class RunControl:
    """Thread-safe pause/stop flags shared between the UI thread and the run thread."""

    def __init__(self):
        self._stop = threading.Event()
        self._running = threading.Event()
        self._running.set()

    def stop(self):
        self._stop.set()
        self._running.set()  # wake a paused run so it can stop

    def pause(self):
        self._running.clear()

    def resume(self):
        self._running.set()

    @property
    def paused(self) -> bool:
        return not self._running.is_set()

    def checkpoint(self):
        self._running.wait()
        if self._stop.is_set():
            raise StopRequested


@dataclass
class Progress:
    event: str  # "page", "record", "skipped", "info"
    pages: int
    records: int
    message: str
    url: str | None = None


@dataclass
class RunResult:
    run_id: int
    status: str  # done | stopped | blocked | disallowed | network_error | no_items
    note: str
    pages: int
    records: int
    requests: int


class _Crawl:
    def __init__(self, store, recipe_id, recipe: Recipe, fetcher, control, on_progress, max_pages, max_records):
        self.store = store
        self.recipe_id = recipe_id
        self.recipe = recipe
        self.fetcher = fetcher
        self.control = control or RunControl()
        self.on_progress = on_progress or (lambda p: None)
        self.max_pages = max_pages
        self.max_records = max_records or recipe.max_records
        self.pages = 0
        self.records = 0
        self.consecutive_empty = 0

    def emit(self, event, message, url=None):
        self.on_progress(Progress(event, self.pages, self.records, message, url))

    def fetch(self, url):
        """Page HTML, or None for a blank page we skip. Several blanks in a row look like a soft block."""
        self.control.checkpoint()
        try:
            html = self.fetcher.get(url)
        except EmptyPageError:
            self.consecutive_empty += 1
            if self.consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                raise BlockedError(f"{self.consecutive_empty} blank pages in a row, last {url}")
            self.emit("skipped", "A page came back empty; it will be retried next run.", url)
            return None
        self.consecutive_empty = 0
        return html

    def limit_reached(self) -> bool:
        return bool(self.max_records) and self.records >= self.max_records

    def run(self) -> str:
        url = self.recipe.start_url
        seen = set()
        previous_signature = None
        while url and url not in seen:
            if self.max_pages and self.pages >= self.max_pages:
                break
            seen.add(url)
            html = self.fetch(url)
            if html is None:
                self.emit("info", "Stopped going through pages because a list page came back empty.", url)
                break
            items = extract_list(html, self.recipe, url)
            self.pages += 1
            if not items:
                if self.pages == 1:
                    return "no_items"
                break
            # Some sites answer an out-of-range page number with the last (or first) page again.
            signature = tuple(sorted((k, v) for k, v in items[0].items() if v))
            if signature == previous_signature:
                break
            previous_signature = signature
            self.emit("page", f"Reading page {self.pages} ({len(items)} items).", url)

            for index, item in enumerate(items):
                if self.limit_reached():
                    return "done"
                self.collect(item, index, url)
            if self.limit_reached():
                return "done"
            url = next_page_url(html, self.recipe, url, self.pages)
        return "done"

    def collect(self, item: dict, index: int, page_url: str):
        detail = self.recipe.detail
        link = item.get(detail.link_field) if detail else None
        key = link if link else f"{page_url}#item{index}"
        if self.store.has_record(self.recipe_id, key):
            return
        data = dict(item)
        if detail and link:
            html = self.fetch(link)
            if html is None:
                return
            data.update(extract_detail(html, self.recipe, link))
        elif detail:
            data.update({f.name: None for f in detail.fields})
        self.store.save_record(self.recipe_id, key, data)
        self.records += 1
        self.emit("record", f"Collected record {self.records} (page {self.pages}).", key)


def run_recipe(store, recipe_id, fetcher, control=None, on_progress=None, max_pages=0, max_records=0) -> RunResult:
    """Run a saved recipe to completion, stop, or block. Always records the run; never raises for site problems."""
    recipe = store.get_recipe(recipe_id)
    crawl = _Crawl(store, recipe_id, recipe, fetcher, control, on_progress, max_pages, max_records)
    run_id = store.start_run(recipe_id)
    status, note = "done", ""
    log.info("run %s started for recipe %s", run_id, recipe_id)
    try:
        status = crawl.run()
        if status == "no_items":
            note = "No items found on the start page. The site may have changed."
    except StopRequested:
        status, note = "stopped", "Stopped by user. Run again to continue."
    except BlockedError as exc:
        status, note = "blocked", str(exc)
    except DisallowedError as exc:
        status, note = "disallowed", f"robots.txt does not allow {exc}"
    except requests.RequestException as exc:
        status, note = "network_error", f"{exc.__class__.__name__}: network problem. Run again to continue."
    finally:
        store.finish_run(run_id, status, fetcher.requests_made, crawl.pages, crawl.records, note)
        log.info("run %s finished: %s, %s requests, %s new records",
                 run_id, status, fetcher.requests_made, crawl.records)
    return RunResult(run_id, status, note, crawl.pages, crawl.records, fetcher.requests_made)
