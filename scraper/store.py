"""SQLite store: page cache (resume point), raw records, run log."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    url TEXT PRIMARY KEY,
    status INTEGER,
    html TEXT,
    fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS records (
    source_url TEXT PRIMARY KEY,
    source TEXT,
    data TEXT,
    collected_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT,
    requests INTEGER,
    listing_pages INTEGER,
    profiles INTEGER,
    note TEXT
);
"""


def now():
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def get_page(self, url):
        row = self.db.execute("SELECT html FROM pages WHERE url = ?", (url,)).fetchone()
        return row[0] if row else None

    def save_page(self, url, status, html):
        self.db.execute(
            "INSERT OR REPLACE INTO pages (url, status, html, fetched_at) VALUES (?, ?, ?, ?)",
            (url, status, html, now()),
        )
        self.db.commit()

    def has_record(self, source_url):
        return self.db.execute("SELECT 1 FROM records WHERE source_url = ?", (source_url,)).fetchone() is not None

    def save_record(self, source, source_url, data):
        self.db.execute(
            "INSERT OR REPLACE INTO records (source_url, source, data, collected_at) VALUES (?, ?, ?, ?)",
            (source_url, source, json.dumps(data, ensure_ascii=False), now()),
        )
        self.db.commit()

    def records(self, source):
        rows = self.db.execute(
            "SELECT source_url, data, collected_at FROM records WHERE source = ? ORDER BY rowid", (source,)
        )
        return [{"source_url": url, "collected_at": at, **json.loads(data)} for url, data, at in rows]

    def start_run(self, source):
        cur = self.db.execute("INSERT INTO runs (source, started_at, status) VALUES (?, ?, 'running')", (source, now()))
        self.db.commit()
        return cur.lastrowid

    def finish_run(self, run_id, status, requests, listing_pages, profiles, note=""):
        self.db.execute(
            "UPDATE runs SET finished_at = ?, status = ?, requests = ?, listing_pages = ?, profiles = ?, note = ? "
            "WHERE id = ?",
            (now(), status, requests, listing_pages, profiles, note, run_id),
        )
        self.db.commit()

    def runs(self, source):
        cur = self.db.execute(
            "SELECT id, started_at, finished_at, status, requests, listing_pages, profiles, note "
            "FROM runs WHERE source = ? ORDER BY id",
            (source,),
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur]
