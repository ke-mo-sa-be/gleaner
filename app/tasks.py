"""Run blocking work (network, disk) off the UI thread and get the result back as a Qt signal.

Daemon threads, so a slow polite pause never keeps the app from closing; an unfinished run is marked
"interrupted" on next start and resumes from the page cache.
"""

import logging
import threading

from PySide6.QtCore import QObject, Signal

from core import paths
from core.fetcher import BlockedError, DisallowedError, EmptyPageError
from core.recipe import RecipeError
from core.updates import UpdateError
from core.store import Store

log = logging.getLogger(__name__)

_alive = set()  # keep signal objects referenced until their task finishes


class _Relay(QObject):
    done = Signal(object)
    failed = Signal(str)


def friendly_error(exc) -> str:
    if isinstance(exc, BlockedError):
        return ("The site refused or challenged the request (it may have blocked this PC). "
                "Gleaner will not keep trying.")
    if isinstance(exc, DisallowedError):
        return "This site asks robots not to collect this page, so Gleaner won't collect it."
    if isinstance(exc, EmptyPageError):
        return "The site sent back an empty page. Try again later."
    if isinstance(exc, RecipeError):
        return "The recipe has problems:\n- " + "\n- ".join(exc.problems)
    if isinstance(exc, UpdateError):
        return str(exc)  # already plain language
    if exc.__class__.__module__.startswith("requests"):
        return "Couldn't reach the site. Check the address and your internet connection."
    return "Something went wrong. Details are in the log file."


def run_task(fn, *args, on_done=None, on_failed=None):
    """Call fn(*args) in a background thread. Callbacks run on the UI thread."""
    relay = _Relay()
    _alive.add(relay)
    if on_done:
        relay.done.connect(on_done)
    if on_failed:
        relay.failed.connect(on_failed)
    relay.done.connect(lambda _r: _alive.discard(relay))
    relay.failed.connect(lambda _m: _alive.discard(relay))

    def work():
        try:
            result = fn(*args)
        except UpdateError as exc:  # expected (offline, no release yet): no stack trace in the log
            log.warning("update check: %s", exc)
            relay.failed.emit(friendly_error(exc))
            return
        except Exception as exc:  # thread boundary: log, then show a plain message
            log.exception("background task failed")
            relay.failed.emit(friendly_error(exc))
        else:
            relay.done.emit(result)

    threading.Thread(target=work, daemon=True).start()


def with_store(fn):
    """Wrap fn(store, ...) so it opens its own SQLite connection in the worker thread."""
    def wrapped(*args):
        store = Store(paths.db_path())
        try:
            return fn(store, *args)
        finally:
            store.close()
    return wrapped
