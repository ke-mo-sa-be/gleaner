# Changelog

All notable changes to Gleaner are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Ad remover in the built-in browser: ads, pop-up ads and trackers from well-known networks are blocked and
  empty ad boxes hidden while you build recipes (and during browser runs). The page itself is never
  changed. Switch it off in Settings > Built-in browser.

## [0.8.0] - 2026-10-16

### Changed

- Cleaner, more modern look across the app: cards, rounded inputs, quieter secondary buttons, thin
  scrollbars, Windows 11 font.
- Recipe builder: browser bar on top (back, forward, reload, address, Open); the right panel shows one
  step at a time (List, Item page, More pages) with ticks when done, and only that step's columns.
  List type and phone country moved under Options; the preview can be folded away.
- Library: New recipe and other library-wide actions on the right of the title; Run, Edit and Export for
  the selected recipe; Duplicate, Share and Delete under More.
- The builder's address bar shows the page that is open, including item pages.
- User-Agent is now `Gleaner/0.8`.

### Known issues

- Releases are not code-signed (internal use), so Windows Smart App Control blocks the installer unless IT
  allows it.

## [0.7.0] - 2026-10-15

### Added

- Sites that build their list with JavaScript: instead of refusing to save, Gleaner saves the recipe for
  browser runs. Runs open each page in Gleaner's own browser (pictures off), wait for the list, and keep
  the same speed, robots and block rules.
- Collapsible sidebar: the menu button (Ctrl+B) shrinks it to icons; remembered between starts.
- Theme button at the bottom of the sidebar on every screen: Match Windows, Light, Dark (Ctrl+Shift+T).
- Sidebar icons.

### Changed

- The built-in browser's User-Agent now includes `Gleaner/0.7`, like Gleaner's other requests.
- The builder takes a second preview 1.5 seconds after a page loads, for pages that fill in late.

### Fixed

- The "Find & delete person..." button showed "Find _delete person..." (the "&" was read as a keyboard
  shortcut).

### Known issues

- Releases are not code-signed yet, so Windows Smart App Control blocks the installer.

## [0.6.0] - 2026-10-15

### Added

- List type "Headings with text below" for directories written as a heading per entry with paragraphs
  under it (blog-style supplier lists). Auto-detect recognises these pages and proposes Name, Address,
  one column per common "Label:" line (Email, Phone, ...) and Website. Clicking a paragraph with
  "Email: / Phone:" lines adds one column per label.
- Image columns: click a picture to collect its web address. Lazy-loaded pictures (`data-src`, `srcset`)
  are understood.
- Phone country per recipe for numbers written without a country code (India +91 by default; Nigeria,
  Kenya, Ghana, South Africa, UAE, Saudi Arabia, UK, USA/Canada and more, or any code).
- Back, Forward and Reload buttons in the Recipe builder (Alt+Left / Alt+Right).
- Library > Find & delete person: search every recipe by phone, email or name, delete the person's
  records and cached pages, and add them to a do-not-collect list (hashes only). Later runs skip them
  without opening their page.
- Optional code signing in the build (`GLEANER_SIGNTOOL_ARGS`) so Smart App Control can run signed
  releases.
- This changelog.

### Changed

- Phone numbers that start with `+` or `00` keep their own country code; a leading trunk `0` is dropped.
- The data file is upgraded automatically to schema version 2 (adds the do-not-collect list).
- User agent is now `Gleaner/0.6`.

### Known issues

- Releases are not code-signed yet. Windows Smart App Control blocks the installer ("An Application
  Control policy has blocked this file"). On a company PC, ask IT to allow Gleaner.

## [0.5.0] - 2026-10-14

### Added

- Auto-detect on list pages (items, fields with names, item link, next page) and item pages
  (label/value fields). Offline heuristics, no AI; sensitive-looking fields are left out.
- Several start pages per recipe (for example one per city), added from the browser or pasted. The Excel
  file has a Start Page column.
- Master list: several recipes in one Excel file, duplicates across recipes by phone, else email.
- Share recipe as a `.json` file and Import recipe.

## [0.4.0] - 2026-10-14

### Added

- First public release: desktop app with Library, point-and-click Recipe builder, Run (pause, stop,
  resume), Guide with a step-by-step tutorial, and Settings.
- Light, dark and Match Windows themes.
- Speed presets Gentle, Normal and Faster (never faster than one page every 3 seconds).
- Update check against the latest GitHub release.
- Polite fetching (robots.txt, one request at a time, stop on block), page cache and resumable runs,
  cleanup of phone, email and pincode columns, Excel export with Records, Needs Review and Run Log sheets.
- Windows installer (per user, no admin rights).

[Unreleased]: https://github.com/ke-mo-sa-be/gleaner/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/ke-mo-sa-be/gleaner/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/ke-mo-sa-be/gleaner/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/ke-mo-sa-be/gleaner/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/ke-mo-sa-be/gleaner/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/ke-mo-sa-be/gleaner/releases/tag/v0.4.0
