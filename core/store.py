"""SQLite access: recipes, runs, page cache, raw records (docs/DATABASE.md)."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from core.recipe import Recipe, from_dict, validate

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    start_url TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    pages INTEGER NOT NULL DEFAULT 0,
    records INTEGER NOT NULL DEFAULT 0,
    note TEXT
);
CREATE INDEX IF NOT EXISTS runs_recipe ON runs(recipe_id, id);
CREATE TABLE IF NOT EXISTS pages (
    url TEXT PRIMARY KEY,
    status INTEGER,
    html TEXT,
    fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    item_key TEXT NOT NULL,
    data TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    UNIQUE (recipe_id, item_key)
);
CREATE INDEX IF NOT EXISTS records_recipe ON records(recipe_id);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    """One Store per thread: each opens its own SQLite connection."""

    def __init__(self, path, allow_local_urls=False):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.allow_local_urls = allow_local_urls  # tests only (local fixture site)
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def _migrate(self):
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            self.db.executescript(SCHEMA)
            self.db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.db.commit()

    def close(self):
        self.db.close()

    # recipes
    def save_recipe(self, recipe: Recipe, recipe_id=None) -> int:
        validate(recipe, allow_local=self.allow_local_urls)
        body = recipe.to_json()
        if recipe_id is None:
            cur = self.db.execute(
                "INSERT INTO recipes (name, start_url, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (recipe.name, recipe.start_url, body, now(), now()),
            )
            recipe_id = cur.lastrowid
        else:
            self.db.execute(
                "UPDATE recipes SET name = ?, start_url = ?, body = ?, updated_at = ? WHERE id = ?",
                (recipe.name, recipe.start_url, body, now(), recipe_id),
            )
        self.db.commit()
        return recipe_id

    def get_recipe(self, recipe_id) -> Recipe:
        row = self.db.execute("SELECT body FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
        if row is None:
            raise KeyError(recipe_id)
        return from_dict(json.loads(row[0]))

    def find_recipe(self, name):
        row = self.db.execute("SELECT id FROM recipes WHERE name = ?", (name,)).fetchone()
        return row[0] if row else None

    def delete_recipe(self, recipe_id):
        self.db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        self.db.commit()

    def list_recipes(self) -> list[dict]:
        cur = self.db.execute(
            """
            SELECT r.id, r.name, r.start_url, r.updated_at,
                   (SELECT COUNT(*) FROM records x WHERE x.recipe_id = r.id) AS record_count,
                   lr.status AS last_status, lr.started_at AS last_run_at
            FROM recipes r
            LEFT JOIN runs lr ON lr.id = (SELECT MAX(id) FROM runs WHERE recipe_id = r.id)
            ORDER BY r.name
            """
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur]

    # page cache
    def get_page(self, url):
        row = self.db.execute("SELECT html FROM pages WHERE url = ?", (url,)).fetchone()
        return row[0] if row else None

    def save_page(self, url, status, html):
        self.db.execute(
            "INSERT OR REPLACE INTO pages (url, status, html, fetched_at) VALUES (?, ?, ?, ?)",
            (url, status, html, now()),
        )
        self.db.commit()

    # records
    def has_record(self, recipe_id, item_key) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM records WHERE recipe_id = ? AND item_key = ?", (recipe_id, item_key)
        ).fetchone()
        return row is not None

    def save_record(self, recipe_id, item_key, data: dict):
        self.db.execute(
            "INSERT OR REPLACE INTO records (recipe_id, item_key, data, collected_at) VALUES (?, ?, ?, ?)",
            (recipe_id, item_key, json.dumps(data, ensure_ascii=False), now()),
        )
        self.db.commit()

    def records(self, recipe_id) -> list[dict]:
        cur = self.db.execute(
            "SELECT item_key, data, collected_at FROM records WHERE recipe_id = ? ORDER BY id", (recipe_id,)
        )
        return [{"item_key": key, "collected_at": at, "data": json.loads(data)} for key, data, at in cur]

    def record_count(self, recipe_id) -> int:
        return self.db.execute("SELECT COUNT(*) FROM records WHERE recipe_id = ?", (recipe_id,)).fetchone()[0]

    # runs
    def start_run(self, recipe_id) -> int:
        cur = self.db.execute(
            "INSERT INTO runs (recipe_id, started_at, status) VALUES (?, ?, 'running')", (recipe_id, now())
        )
        self.db.commit()
        return cur.lastrowid

    def finish_run(self, run_id, status, requests, pages, records, note=""):
        self.db.execute(
            "UPDATE runs SET finished_at = ?, status = ?, requests = ?, pages = ?, records = ?, note = ? WHERE id = ?",
            (now(), status, requests, pages, records, note, run_id),
        )
        self.db.commit()

    def runs(self, recipe_id) -> list[dict]:
        cur = self.db.execute(
            "SELECT id, started_at, finished_at, status, requests, pages, records, note "
            "FROM runs WHERE recipe_id = ? ORDER BY id",
            (recipe_id,),
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur]

    def last_run(self, recipe_id):
        runs = self.runs(recipe_id)
        return runs[-1] if runs else None

    def mark_interrupted(self) -> int:
        """Runs left 'running' by a crash or forced close. Call once at app start."""
        cur = self.db.execute(
            "UPDATE runs SET status = 'interrupted', finished_at = ? WHERE status = 'running'", (now(),)
        )
        self.db.commit()
        return cur.rowcount
