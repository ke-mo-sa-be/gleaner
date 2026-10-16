# Gleaner

Point-and-click Windows app that collects listings from directory-style websites (businesses, shops,
products, members, professionals, ...) into clean Excel files, politely and safely. No programming needed. Product and technical decisions live in [docs/](docs/); agent rules in
[AGENTS.md](AGENTS.md).

| Doc | What it answers |
|---|---|
| [User guide](docs/USER_GUIDE.md) | How to use Gleaner (also inside the app: Guide) |
| [PRD](docs/PRD.md) | What we are building, scope, open questions |
| [UX_FLOWS](docs/UX_FLOWS.md) | How users build and run recipes |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Components and decisions |
| [DATABASE](docs/DATABASE.md) | SQLite schema and recipe JSON format |
| [SECURITY](docs/SECURITY.md) | Site Safety Rules, personal data handling |
| [DESIGN_SYSTEM](docs/DESIGN_SYSTEM.md), [CODE_STYLE](docs/CODE_STYLE.md), [TESTING](docs/TESTING.md) | UI, code and test conventions |

## Status

Full history: [CHANGELOG.md](CHANGELOG.md).

- v0.9: Ad remover, Update now (verified in-app update), columns shown on the page, better heading lists.
- v0.8: Cleaner, modern UI; step-based Recipe builder (List, Item page, More pages); simpler Library.
- v0.7: Sites that build their list with JavaScript (runs open pages in Gleaner's browser), collapsible
  sidebar, theme button on every screen.
- v0.6: Directories written as headings and paragraphs, image columns, phone country per recipe, Back /
  Forward in the builder, Find & delete person with a do-not-collect list, optional code signing in the build.
- v0.5: Auto-detect (list, fields, item link, next page, item-page labels), several start pages per recipe,
  master list across recipes, share recipes as files.
- v0.4: engine (recipes, polite fetcher, extraction, resumable runner, cleanup, Excel export); desktop app
  (Library, point-and-click Recipe builder, Run with speed choice, Guide, Settings with light/dark theme and
  update check); Windows installer.
- 123 automated tests including offscreen UI tests.
- Next: see "Future" in [docs/PRD.md](docs/PRD.md) section 8.

## Setup

Requires Python 3.12+.

```
py -m pip install -r requirements.txt
```

## Desktop app

```
py -m app
```

Library lists recipes; **New recipe** opens the builder: type the site address, Open, then click
**Auto-detect** (or **+ Add list field** and click an example on the page). **Mark item link** and **+ Add item field** collect
values from each item's own page; **Mark next page** makes Gleaner go through every page. Save, then Run.
The **Guide** screen has a step-by-step tutorial, including sites with many layers.

## Windows installer

```
py packaging/build.py
```

Runs the tests, packs the app with PyInstaller (`dist/Gleaner/`) and builds
`dist/installer/Gleaner-Setup-<version>.exe` with Inno Setup 6 (`winget install JRSoftware.InnoSetup --scope user`).
The installer needs no admin rights, adds a Start-menu shortcut and an uninstaller. Uninstalling keeps the user's
recipes, collected data and Excel files. Version: `app/__init__.py`.

## Releasing a new version

1. Bump `__version__` in `app/__init__.py`, then `py packaging/build.py`.
2. Publish the installer as a GitHub release (the app's update check reads the latest release):

```
gh release create v0.4.0 dist/installer/Gleaner-Setup-0.4.0.exe --title "Gleaner 0.4.0" --notes "What changed"
```

Users see "Gleaner 0.4.0 is available" at start-up (or Settings > Updates > Check now), download and run the
installer over the old version. Their recipes, data and Excel files are kept. Without internet access to
GitHub, point Settings > Update source at a shared folder containing `latest.json`
(`{"version": "0.4.0", "url": "Gleaner-Setup-0.4.0.exe", "notes": "..."}`) and the installer.

## Engine command line

```
py -m core import recipes/drdata.json
py -m core list
py -m core run "drdata.in doctors" --max-records 20
py -m core export "drdata.in doctors"
```

Data lives in `%LOCALAPPDATA%\Gleaner\`, Excel files go to `Documents\Gleaner\`.
Set `GLEANER_HOME` to keep both in another folder (development).

Workbook sheets: **Records** (ready to use), **Needs Review** (missing required field or duplicate; the
Issues column says why), **Run Log** (every run and its outcome).

## Site Safety Rules (built in, not settings)

One request at a time, 5-10 s apart by default (Gentle 10-20 s, Faster 3-5 s; never under 3 s); robots.txt obeyed; any block signal stops the run
at once; no proxies, IP rotation or CAPTCHA solving. Details: [docs/SECURITY.md](docs/SECURITY.md).

## Tests

```
py -m unittest discover -s tests -t .
```

Automated tests use a local fake site only; they never contact real websites.

## Legacy

`scraper/` is the first command-line MVP (drdata.in only, `py -m scraper drdata ...`). It is replaced by
the `core` engine and will be removed once the desktop app is in use.
