# Testing

## 1. Testing Goals

Critical functionality:
- Site Safety Rules (delay floor, robots.txt, block detection, stop-on-block)
- Recipe extraction (list items, fields, label-anchored fields, pagination, detail links)
- Picker selectors evaluate identically in the browser and in BeautifulSoup
- Cleaning (phone, email, pincode), dedup and Needs Review split
- Resume after interruption

## 2. Test Types

### Unit Testing
`core` modules against small synthetic HTML strings. No network, no Qt.

### Integration Testing
Runner end-to-end against a **local fixture site** (`tests/integration/fixture_site.py`: stdlib
`http.server` on 127.0.0.1, started by each test, synthetic data generated in code) with listing pages,
both pagination styles, detail pages, a robots.txt-disallowed path, a blank-page route, a 429 route and an
empty listing. The delay floor is lowered only through a test-only fetcher
argument, never a user setting. Never hit real websites in automated tests.

### End-to-End Testing
Offscreen Qt (`QT_QPA_PLATFORM=offscreen`, no window opens):
- `tests/ui/test_picker.py`: picker selectors on synthetic pages extract the same values in the browser
  and in `core.extract`; page scripts cannot see the picker.
- `tests/ui/test_builder.py`: the Builder screen end to end against the fixture site: pick a list
  field, mark the item link, pick a labelled item field, mark next page, save, run the saved recipe.
- `tests/ui/test_app_shell.py`: main window sections, Guide routing, settings storage, light/dark theme
  switch, per-run speed default; speed presets never below the 3 s floor.
- `tests/unit/test_updates.py`: version comparison, shared-folder manifest, GitHub latest release (mocked).
- `tests/unit/test_master.py`: master list columns, cross-recipe duplicates, workbook sheets.
- Start pages: recipe format and validation (`test_recipe.py`), runs across start pages with per-start
  pagination and limits (`test_runner.py`), builder add/paste/save/run (`test_builder.py`).
- Auto-detect: tables, cards, item pages, link-heavy page noise (`test_picker.py`), builder flow end to end
  (`test_builder.py`).
- Heading lists and images (v0.6): section extraction, label lines, lazy images (`test_extract.py`);
  picker auto-detect and manual picks on a synthetic article page (`test_picker.py`); builder auto-detect,
  phone country, save and run against `/sections` (`test_builder.py`); back / forward / reload
  (`test_builder.py`). Phone country rules (`test_clean.py`).
- Find & delete person (v0.6): matching, hashed keys and the version 1 to 2 schema upgrade
  (`test_privacy.py`); delete then re-run skips the person without fetching their page (`test_runner.py`);
  dialog (`test_app_shell.py`).
UI tests are skipped when PySide6 is not installed. Look-and-feel is checked manually (section 5).

Critical journeys:
- Build recipe (list + pagination + detail)
- Run recipe to completion and open Excel
- Run stops on block
- Resume after closing the app mid-run

## 3. Testing Tools

Unit: `unittest` (stdlib), run via `py -m unittest`
Integration: `unittest` + stdlib `http.server`
E2E: manual checklist + offscreen QtWebEngine picker tests

## 4. Test File Structure

```
tests/
  unit/            test_recipe.py, test_extract.py, test_clean.py, test_fetcher.py, ...
  integration/     fixture_site.py, test_runner.py
  ui/              test_picker.py, test_builder.py, test_app_shell.py (offscreen Qt)
  test_scraper.py  legacy CLI tests (removed with scraper/)
```

## 5. Critical User Flows (manual, before each release)

Flow: Build drdata recipe
Steps:
1. New Recipe, URL `https://www.drdata.in/list-doctors.php?specialization=Radiologist`
2. Pick Name, Specialization, Degree, State, City; mark next page; mark detail link; pick Phone (label),
   Clinic, Address, Registration Number (label)
3. Save
Expected result: Preview matches the website for 10 rows; saved recipe equals `recipes/drdata.json`
in structure.

Flow: Run with limits
Steps:
1. Run drdata recipe with max records 20
2. Open Excel
Expected result: 20 rows across Records + Needs Review; Run Log row status `done`; phones `+91...`.

Flow: Block handling
Steps:
1. Run a recipe against the fixture site's 429 route
Expected result: Run stops within one request, red banner, status `blocked`, badge in Library.

Flow: Resume
Steps:
1. Start a run, close the app after ~5 records, reopen, Run again
Expected result: "Continuing..." message; no cached page refetched; total records continue.

## 6. Coverage

Target: no numeric gate in MVP; every `core` module has unit tests; every Site Safety Rule has a test.
Prioritize:
- Site Safety Rules
- Extraction and cleaning logic
- Data mutations (store, migrations)
- Important user journeys

## 7. Commands

Test: `py -m unittest discover -s tests -t .`
Lint: `py -m ruff check .`
Format: `py -m ruff format .`
Build installer: `py packaging/build.py` (tests, PyInstaller, Inno Setup)
Run app: `py -m app`

## 8. Definition of Done

- [ ] Tests pass
- [ ] Lint passes
- [ ] Installer builds, installs, starts and uninstalls cleanly
- [ ] Critical flow verified manually where UI changed
- [ ] No blocking errors in the log
