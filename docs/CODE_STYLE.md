# Code Style & Conventions

## 1. General Principles

- Prefer readable code
- Keep functions focused
- Avoid unnecessary abstractions
- Reuse existing modules (`core.fetcher`, `core.clean`, `core.export`) instead of new helpers
- Prefer consistency over novelty

## 2. Naming

Classes: PascalCase (`Recipe`, `RunView`)
Functions / methods: snake_case
Variables: snake_case
Constants: UPPER_SNAKE_CASE
Files / modules: snake_case.py
Database fields: snake_case
Qt signals: snake_case nouns or past tense (`page_loaded`, `progress`)
Recipe JSON keys: snake_case

## 3. Folder Structure

- `core/` - engine, no Qt. One module per responsibility (see ARCHITECTURE.md 4).
- `app/` - UI only. One module per view (`library_view.py`, `builder_view.py`, `run_view.py`),
  shared widgets in `app/widgets.py`, `picker.js` next to the builder.
- `tests/unit/`, `tests/integration/` mirror `core/` module names (`test_extract.py`).

## 4. Imports

- Standard library, third-party, local - separated by blank lines.
- Absolute imports within packages (`from core.recipe import Recipe`).
- `core` never imports `app` or PySide6.

## 5. Components (Qt)

Widgets should:
- Have a single responsibility
- Talk to `core` through plain function calls; long work runs in a worker (`QThread`) and reports via
  signals
- Never block the UI thread with network or disk-heavy work

## 6. Functions

Functions should:
- Do one logical thing
- Have type hints on public `core` functions
- Return values rather than mutate arguments, except store/IO methods

## 7. Error Handling

Use: specific exception classes in `core` (`BlockedError`, `DisallowedError`, `EmptyPageError`,
`RecipeError`); the UI maps them to plain-language messages (UX_FLOWS.md).
Do not: catch bare `Exception` except at thread/UI boundaries, where it is logged with traceback and
shown as a generic error banner.

## 8. Comments

Comments should explain:
- Why something exists
- Important tradeoffs
- Non-obvious behavior (site quirks, selector restrictions)
Avoid comments that simply repeat the code.

## 9. Logging

Use: stdlib `logging`, logger per module (`log = logging.getLogger(__name__)`).
Rules:
- No personal data in log messages (log counts and URLs, not names/phones).
- INFO for run lifecycle, WARNING for retries/skips, ERROR for stops.

## 10. Formatting

Formatter: `ruff format` (line length 110)
Linter: `ruff check`
Type Checking: none enforced in MVP; type hints on public `core` APIs

## 11. Do

- Reuse existing patterns
- Keep changes focused
- Follow project conventions
- Remove dead code (delete `scraper/` once the app reaches parity)

## 12. Don't

- Create duplicate utilities
- Introduce unnecessary dependencies (ask before adding any package)
- Ignore existing architecture
- Change unrelated files
- Weaken or bypass the Site Safety Rules (SECURITY.md 3)
