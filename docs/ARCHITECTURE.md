# Architecture

## 1. System Overview

A single-user Windows desktop application. A Qt UI hosts an embedded Chromium browser (QtWebEngine) used
by the Recipe Builder. A JavaScript picker injected into the page turns clicks into CSS selectors. Recipes
are stored as JSON. A background runner fetches pages politely (plain HTTP, or the embedded browser when a
site needs JavaScript), extracts fields with the recipe's selectors, stores raw records in SQLite, then
cleans and exports them to Excel.

## 2. Architecture Pattern

Pattern: Modular monolith (one process; `core` package with no UI dependencies + `app` UI package).
Reason: One user, one PC, no server. Keeping `core` free of Qt makes it testable without a display and
reusable by the existing CLI.

## 3. Technology Stack

Frontend: PySide6 (Qt Widgets) + QtWebEngine (embedded Chromium)
Backend: Python 3.12+ (same process)
Database: SQLite (stdlib `sqlite3`)
Authentication: None (single local user; Windows login is the boundary)
Storage: Local files under `%LOCALAPPDATA%\Gleaner\` (db, cache, logs) and
`Documents\Gleaner\` (Excel exports)
Hosting: None (desktop). Packaged with PyInstaller; optional Inno Setup installer
HTTP: `requests`
HTML parsing / extraction: `beautifulsoup4` (+ soupsieve CSS selectors)
Excel: `openpyxl`
Other Services: none in MVP. Future AI feature: Anthropic API (optional, off by default)

## 4. System Components

### app (UI) - `app/`
Responsibilities:
- Main window with Library, Builder and Run views.
- Builder: host QWebEngineView, inject `picker.js` (isolated script world), receive picks over a
  token-tagged console bridge (`app/web.py`), show field panel and preview table.
- Run view: start/pause/stop a run in a background daemon thread, show progress via Qt signals; per-run
  speed choice.
- Settings view (`app/settings_view.py`) and preferences (`app/settings.py`, stored in
  `<data folder>\settings.ini`): theme, default speed, Excel folder, update source.
- Guide view (`app/help_view.py`): renders docs/USER_GUIDE.md chapter by chapter.
- Theme (`app/style.py`): light/dark palettes, follows Windows when set to Match Windows.
- Never parses HTML or touches SQLite directly; calls `core` services.

### picker - `app/picker.js`
Responsibilities:
- Hover outline and click capture in pick mode (page's own click handlers suppressed while picking).
- Generalise a clicked element into (item selector, field selector) pairs; count matches; highlight.
- Return selectors that BeautifulSoup/soupsieve can evaluate (tags, classes, attributes,
  `:nth-of-type`; no `:has()`, no XPath).
- Heading lists (v0.6): the same section rule as `core/extract.py sections()` (heading + following
  siblings); selectors are relative to the section wrapper (`:scope > p:nth-of-type(2)`).

### core - `core/`
Responsibilities:
- `recipe.py`: recipe dataclasses, JSON (de)serialisation, validation.
- `fetcher.py`: polite fetching, robots.txt, block detection, page cache (moved from `scraper/`).
- `extract.py`: apply a recipe to HTML: list items, fields, label-anchored fields, next-page URL,
  detail URLs.
- `runner.py`: crawl loop driven by a recipe; emits progress events through a callback; supports
  pause/stop via a control object; no Qt imports.
- `clean.py`: type-based cleanup (phone, email, pincode, number), dedup, required-field checks
  (generalised from `scraper/validate.py`).
- `export.py`: Excel writer.
- `updates.py`: read-only check of the update source (GitHub latest release or latest.json).
- `store.py`: SQLite access (recipes, runs, pages, records, suppressions).
- `privacy.py`: find & delete person matching and the hashed do-not-collect keys.

### Database
Responsibilities:
- Persist recipes, run history, page cache and raw records (see DATABASE.md).

## 5. Architecture Diagram

```
 Builder (Qt) ── QWebEngineView ── picker.js (isolated world)
     │   ▲            picks via token-tagged console messages
     ▼   │
 core.recipe ──► core.store (SQLite)
                     ▲
 Run view (Qt) ── thread ── core.runner ──► core.fetcher ──► website
                                 │                 │
                                 ▼                 ▼ (render_js recipes)
                           core.extract      RenderBridge (QtWebEngine, main thread)
                                 │
                                 ▼
                    core.clean ──► core.export ──► Excel
```

## 6. Data Flow

Building:
1. User clicks an element in pick mode.
2. `picker.js` computes selectors and match count, highlights matches, sends a pick message.
3. Builder updates the in-memory recipe and asks `core.extract` to preview using the page's current HTML.
4. On Save, `core.recipe.validate()` runs, then `core.store` writes the recipe JSON.

Running:
1. Run view starts `core.runner` in a daemon thread with the recipe and limits.
2. Runner asks `core.fetcher` for the start page (cache first, then network after the polite delay).
3. `core.extract` returns item rows, detail URLs and next-page URL.
4. For each new detail URL, fetch and extract detail fields; store raw record.
5. Follow next-page URL until none, a repeat, or a limit.
6. On finish/stop/block, record the run, then `core.clean` + `core.export` write Excel.
7. Progress events flow to the UI via Qt signals.

## 7. Project Structure

```
app/            Qt UI (views, widgets, picker.js, render bridge)
core/           UI-free engine (recipe, fetcher, extract, runner, clean, export, store)
recipes/        Example recipes shipped with the app (drdata.json)
scraper/        Legacy CLI MVP (drdata only); kept until the app reaches parity, then removed
tests/          unit/ and integration/ (local fixture site)
docs/           This documentation
packaging/      PyInstaller spec, installer script
```

## 8. Dependency Rules

- `core` must not import PySide6 or anything from `app`.
- `app` must not run SQL or parse HTML itself; it calls `core`.
- All network access goes through `core.fetcher` (or the RenderBridge, which still uses the fetcher's
  robots/delay/block rules). No other module opens connections to target sites.
- Safety constants (minimum delay, block markers) live only in `core/fetcher.py`.

## 9. Key Technical Decisions

Decision: Desktop app with PySide6/QtWebEngine.
Context: Point-and-click needs to load arbitrary third-party sites; a normal web app cannot embed most
sites (X-Frame-Options / CSP).
Alternatives: Electron (would require rewriting the Python engine in Node); local web app + Playwright
window (two windows, extra browser download); off-the-shelf tools (Octoparse, ParseHub, WebScraper.io).
Reason: Reuses the proven Python engine, one window, one installer, no separate browser download.

Decision: Selectors are CSS, generated in the browser, evaluated in Python with BeautifulSoup.
Context: Extraction must work on raw HTML during runs, without a browser, for speed.
Alternatives: XPath (needs lxml), running every page in a browser (slow).
Reason: CSS is readable, soupsieve supports the subset we generate; picker restricted to that subset.

Decision: Plain HTTP for runs; sites that build their list with JavaScript are not supported in MVP.
Context: Some sites build content with JavaScript after the page loads.
Reason: On Save the builder fetches the start page once as the runner will (plain HTTP) and refuses to
save if no items are found there. `render_js` and a RenderBridge (fetch through QtWebEngine) are reserved
for a later version.

Decision: Picker results travel as console messages tagged with a random per-session token.
Context: QWebChannel needs its script exposed to the page; the picker runs in an isolated world instead.
Reason: Page scripts can neither call the picker nor forge a message without the token.

Decision: Background work runs in daemon threads; the shared fetcher clock paces all of them.
Context: A polite pause or retry can sleep up to a minute; the app must still close at once.
Reason: Unfinished runs are marked `interrupted` on next start and resume from the page cache. One
process-wide clock in `core/fetcher.py` keeps "one request at a time" true across a run and builder
previews.

Decision: Heading lists are extracted as virtual sections.
Context: Many directories are articles: a heading per entry with paragraphs (and ads) in between, no
element wraps one entry.
Reason: `extract.sections()` groups a heading with its following siblings into a detached wrapper `<div>`,
so the normal field machinery (selectors, labels, `:scope`) works unchanged and stays CSS.

Decision: Do-not-collect list stores hashes, not values.
Context: An erasure request must stop future collection without keeping the person's data.
Reason: SHA-256 of normalised phone (last 9 digits), email and item key are enough to recognise the person
on later runs and can't be read back.

Decision: Label-anchored detail fields.
Context: Profile pages often use label/value rows whose order varies between profiles (seen on drdata.in).
Reason: A field can be "value next to the label 'Phone Number'" instead of a positional selector.

## 10. Performance Considerations

- Throughput is bounded by the polite delay (5-10 s per request): ~400-700 pages/hour. This is intended.
- Extraction and export must handle 50,000 records per recipe without freezing the UI (work off the UI
  thread).

## 11. Scalability Considerations

- One run per app instance. Several PCs can run different recipes.
- SQLite cache grows with pages; Library offers "Clear cached pages" per recipe (records are kept).

## 12. Failure Scenarios

What happens if:
- Database is unavailable / locked: show "Can't open Gleaner's data file. Close other copies of
  the app." and do not start the run.
- Network drops / request times out: retry twice (30 s, 60 s), then stop the run as "Stopped - network
  problem"; re-run resumes.
- Site sends a block signal: stop immediately, no retry, mark run Blocked (UX Flow 5).
- Site layout changed (0 items on start page): stop with "No items found" (UX Flow 4 empty state).
- Excel file locked: write to a new file name.
- App crashes mid-run: run row stays "running"; on next start the app marks it "interrupted"; re-run
  resumes from the cache.

## 13. Distribution and updates

- `py packaging/build.py`: tests, PyInstaller one-folder app (`dist/Gleaner/`), optional signing
  (`GLEANER_SIGNTOOL_ARGS`, see SECURITY.md 12), Inno Setup per-user installer
  (`dist/installer/Gleaner-Setup-<version>.exe`, no admin rights, same AppId so it upgrades in place).
- Version: `app/__init__.py`. Release: `gh release create v<version> <installer>` on the public repo.
- The app reads the latest release (`core/updates.py`, default source `github:ke-mo-sa-be/gleaner`) and offers
  the download. Installing over the old version keeps `%LOCALAPPDATA%\Gleaner` and the Excel folder.
