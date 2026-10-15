# Database

## 1. Database Engine

Database: SQLite 3 (Python stdlib `sqlite3`), WAL mode
Hosting: Local file `%LOCALAPPDATA%\Gleaner\collector.db`
(Tests and development use a temporary path passed explicitly.)

## 2. Naming Conventions

Tables: snake_case plural (`recipes`, `runs`)
Columns: snake_case
Primary Keys: `id INTEGER PRIMARY KEY` (except `pages`, keyed by `url`)
Foreign Keys: `<table_singular>_id`
Timestamps: ISO 8601 local time, seconds precision, TEXT (`2026-10-14T15:04:05`)

## 3. Tables

### recipes
Purpose: Saved recipes.
Columns: id, name, start_url, body (JSON, see section 13), created_at, updated_at

### runs
Purpose: One row per run attempt; drives Run Log sheet and Library status.
Columns: id, recipe_id, started_at, finished_at, status, requests, pages, records, note
status values: `running`, `done`, `stopped`, `blocked`, `disallowed`, `network_error`, `interrupted`,
`no_items`

### pages
Purpose: Page cache and resume point. A cached page is never fetched again unless refreshed.
Columns: url, status, html, fetched_at

### records
Purpose: Raw extracted values (uncleaned) per item.
Columns: id, recipe_id, item_key, data (JSON object field_name -> raw string or null), collected_at

### suppressions (schema version 2, v0.6)
Purpose: Do-not-collect list for people deleted with Find & delete person. Runs skip any item whose keys
match. Holds hashes only, never the phone numbers, emails or names themselves.
Columns: id, kind (`phone`, `email`, `item`, `name`), value_hash (SHA-256 hex, unique), created_at
Keys hashed (`core/privacy.py`): `phone:<last 9 digits>` of every phone-type field, `email:<lower-case
email>` found in any field, `item:<recipe id>:<item_key>` when the item has its own page, and
`name:<recipe id>:<first column, case-folded>` for items without their own page.

## 4. Relationships

recipes → runs: One recipe has many runs.
recipes → records: One recipe has many records.
pages are shared by URL across recipes (no foreign key).

## 5. Constraints

Required:
- recipes.name, recipes.start_url, recipes.body
- runs.recipe_id, runs.started_at, runs.status
- records.recipe_id, records.item_key, records.data
Unique:
- recipes.name
- (records.recipe_id, records.item_key)
Foreign Keys:
- runs.recipe_id → recipes.id ON DELETE CASCADE
- records.recipe_id → recipes.id ON DELETE CASCADE

`item_key` is the detail-page URL when the recipe has a detail step, otherwise
`<listing page URL>#<item index>`.

## 6. Indexes

Index: runs(recipe_id, id)
Reason: Library shows last run per recipe.
Index: records(recipe_id)
Reason: Export reads all records of one recipe.
Index: suppressions(value_hash) (unique constraint)
Reason: Every collected item is checked against the list.

## 7. Data Validation

- Recipe body must pass `core.recipe.validate()` before insert/update.
- records.data holds raw strings only; cleaning happens at export so rules can change without refetching.
- Run counters are non-negative integers.

## 8. Soft Delete

Does the system use soft deletion? No
Deleting a recipe deletes its runs and records (cascade). Cached pages remain until "Clear cache".
Exported Excel files are never deleted by the app.
Find & delete person hard-deletes the person's records, their cached item page, and cached pages that
contain their email or name, and adds their hashes to `suppressions`.

## 9. Auditing

Do we record:
- Created by? No (single-user app).
- Updated by? No.
- Deleted by? No.
- Activity history? Yes: `runs` table (what, when, outcome, counts), exported as the Run Log sheet.

## 10. Sensitive Data

Sensitive fields:
- records.data (names, phone numbers, emails, addresses of individuals)
- pages.html (same data, raw)
Protection: Stored only on the local PC under the user's profile. Not logged. Not sent anywhere.
See SECURITY.md for retention and handling.

## 11. Migration Rules

History: version 1 = recipes, runs, pages, records. Version 2 (v0.6) adds `suppressions`.

Schema changes must:
1. Be documented here
2. Have a migration in `core/store.py` keyed on `PRAGMA user_version`
3. Be tested (open an old-version database fixture, migrate, read)
4. Avoid breaking existing data (no destructive migrations without an export first)

## 12. Seed Data

Shipped example recipe `recipes/drdata.json` is imported into the library on first start if no recipe
named "drdata.in doctors" exists.

## 13. Recipe JSON format (recipes.body)

```json
{
  "version": 1,
  "name": "drdata.in doctors",
  "start_url": "https://www.drdata.in/list-doctors.php?search=Doctor&specialization=Radiologist",
  "render_js": false,
  "list": {
    "item_selector": "#no-more-tables tbody tr",
    "fields": [
      {"name": "Name", "selector": "td[data-title=\"Name\"]", "attr": "text", "type": "text", "required": true},
      {"name": "Profile", "selector": "a", "attr": "href", "type": "link", "required": false}
    ]
  },
  "pagination": {"type": "page_param", "param": "page", "start": 1, "max_pages": 0},
  "detail": {
    "link_field": "Profile",
    "fields": [
      {"name": "Phone", "label": "Phone Number", "label_scope": "#profile table tr", "type": "phone", "required": true},
      {"name": "Clinic", "label": "Clinic/ Hospital Name", "label_scope": "#profile table tr", "type": "text", "required": false}
    ]
  },
  "dedup_keys": ["Phone"],
  "limits": {"max_records": 0}
}
```

Field rules:
- `attr`: `text` (visible text, whitespace collapsed), `href`/`src` (resolved to absolute URL), or any
  attribute name.
- `type`: `text`, `link`, `image`, `phone`, `email`, `pincode`, `number` - controls cleanup in export.
  `link`/`image` keep a web address (from the attribute, or the first address in the text). Images use
  `attr: "src"`; lazy-loaded pictures (`data-src`, `data-lazy-src`, `srcset`) are understood.
- A field has either `selector` (relative to the list item, or to the page for detail fields) or
  `label` + `label_scope` (detail only: find the row in `label_scope` whose first cell text equals
  `label` (whitespace-insensitive), take the next cell's text).
- `pagination.type`: `none`; `next_link` (`selector` matches the Next link, optionally narrowed by `text`,
  the link's visible text compared case- and whitespace-insensitively; follow its `href`);
  `page_param` (`param`, `start`; increments a URL query parameter).
- `pagination.max_pages` and `limits.max_records`: 0 means no limit.
- `start_urls` (optional, v0.5): several start pages. When present, a run goes through each in order (with
  pagination restarting per start page) and `start_url` equals the first one. Up to 500, no duplicates.
- `list.item_mode` (optional, v0.6): `elements` (default; each `item_selector` match is one item) or
  `sections` (a directory written as headings and paragraphs: `item_selector` matches the headings; an
  item is the heading plus the following siblings up to the next list heading or any heading of the same
  or a higher level; scripts and styles are skipped). In `sections` mode, field selectors are relative to
  that group: `:scope > h3:nth-of-type(1)` is the heading, `:scope > p:nth-of-type(2)` the second
  paragraph, `:scope` the whole section. List fields may then use `label` without `label_scope`: the value
  after "Label:" on a line of the section's text; a value ending in a comma continues on the next line.
- `phone_country` (optional, v0.6, default `"91"`): 1-3 digit country calling code used for phone numbers
  written without one. Numbers starting with `+` or `00` keep their own code; a leading trunk `0` is
  dropped. Export writes `+<code><number>`.
- Each stored record's `data` also holds `_start_page`: the start page it was found from (exported as the
  "Start Page" column).
