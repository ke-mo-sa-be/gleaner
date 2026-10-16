# Security Guidelines

Gleaner is a single-user local desktop app. The main risks are (1) harming or being banned by the
sites we collect from, (2) mishandling personal data of the people in the collected lists, and
(3) leaking anything sensitive from the PC.

## 1. Authentication

Authentication Provider: None. The Windows user account is the boundary.
Website sign-in: The app never automates logins and never stores website passwords. If a team member
has a legitimate account on a site, they may sign in by hand inside the app's browser; the session
cookie lives in the app's browser profile under `%LOCALAPPDATA%\Gleaner\browser\`.

## 2. Authorization

Roles: none in MVP (single user). Owner approval of new sites is an open question (PRD 12).

## 3. Site Safety Rules (non-negotiable)

These are product requirements, not settings. They are enforced in `core/fetcher.py` only.
- One request at a time per app instance.
- Random delay between requests, default 5-10 s; hard floor 3 s.
- robots.txt fetched and obeyed for every host; disallowed URL = stop.
- Block signals stop the run with no retry: HTTP 401/403/407/429/503, Cloudflare challenge or ban pages
  (`cf-chl-`, `error code: 1006`/`1015`), CAPTCHA/"access denied" pages, 3 blank pages in a row.
- Never: proxies, VPN switching, IP rotation, user-agent rotation to evade detection, CAPTCHA solving,
  headless-detection evasion, or retrying after a block.
- The User-Agent includes the token `Gleaner` so site owners can identify the tool, also in the built-in
  browser (builder and browser runs).
- Browser runs (`render_js` recipes, v0.7) obey the same rules: one page at a time on the shared clock,
  robots.txt checked for each page, block signals (HTTP status from the browser, challenge and CAPTCHA
  text) stop the run. Pictures are not loaded. No stealth: the browser is not disguised and never tries to
  hide that it is automated.
- Ad remover (v0.9): the built-in browser drops requests to a bundled list of ad and tracking networks
  (`app/adblock_hosts.txt`) and hides empty ad boxes. It only removes third-party requests, so it lowers the
  load a page puts on other servers; it never touches the site's own requests, never changes the page's HTML
  and is not used to get around blocks or paywalls. Users can switch it off in Settings.
- A recipe whose last run was blocked requires explicit confirmation to run again (UX Flow 5).

## 4. Secrets

- Never hard-code credentials
- Never commit production secrets
- Never expose private secrets
- MVP has no secrets. Future AI key: stored in Windows Credential Manager via `keyring`, never in
  files, recipes, logs or the database.
- Rotate compromised credentials

## 5. Environment Variables

Public: `GLEANER_HOME` (optional override of the data folder, for tests/dev)
Private: none in MVP

## 6. Input Safety

- Start URLs must be `http`/`https`. `file:`, `javascript:` and local network addresses
  (localhost, 127.0.0.0/8, 10/8, 172.16/12, 192.168/16) are rejected, except in tests via an explicit
  flag.
- Recipe JSON is validated against the schema before use; unknown keys rejected.
- Collected HTML is never rendered in the app's own UI as HTML (only as plain text in tables).
- `picker.js` runs inside the page's context and must not send page data anywhere except the app over
  QWebChannel.

## 7. Data Protection (personal data - DPDP Act 2023)

Sensitive data: names, phone numbers, emails and addresses of individual doctors and staff.
- Data minimisation: the builder warns when a field name or value looks like date of birth, Aadhaar,
  PAN, bank or card numbers, and such fields are excluded unless the Owner explicitly keeps them.
- Storage: local only (`%LOCALAPPDATA%\Gleaner\`, `Documents\Gleaner\`). No cloud sync.
- Retention: "Delete recipe data" removes records and cached pages for a recipe. Recommended policy:
  delete raw cache 90 days after export (Owner to confirm).
- Deletion requests (v0.6): Library > "Find & delete person" searches every recipe's records by phone
  (any format, last 9 digits), email or name; the user ticks the records, which are hard-deleted together
  with the cached item page and cached pages containing the person's email or name. The person goes on a
  do-not-collect list (`suppressions` table) holding only SHA-256 hashes of their phone numbers, emails
  and item key; later runs skip them before fetching their item page. Earlier Excel exports are not touched:
  the app tells the user to delete or edit those by hand. Skip messages contain no personal data.
- Use: exports carry a note in the Run Log sheet: "Personal data - scrub against DND before calls/SMS,
  include opt-out, delete on request."

## 8. Logging

Never log:
- Passwords, cookies, API keys, tokens
- Collected personal data (names, phones, emails, addresses)

Log:
- Run start/stop/outcome, counts, URLs fetched (URLs may contain names in slugs; logs are local only)
- Block signals with status code and marker
- Errors with stack traces (log file only, never in the UI)

Log location: `%LOCALAPPDATA%\Gleaner\logs\`, rotated at 5 MB x 5 files.

## 9. File Handling

- The app reads only its own data folder and recipe JSON files the user imports.
- Imported recipe files: `.json`, max 1 MB, validated before use.
- Exports: `.xlsx` only, written to the exports folder; never overwrite an existing file.

## 10. Security Checklist

- [ ] Site safety rules enforced and covered by tests
- [ ] No credentials stored by the app
- [ ] Recipe and URL input validated
- [ ] Personal data not logged
- [ ] Sensitive-field warning in builder
- [ ] Errors in UI do not expose stack traces
- [ ] Dependencies pinned and reviewed (requirements.txt)

## 11. Speed presets

Users choose Gentle (10-20 s), Normal (5-10 s, default) or Faster (3-5 s) between requests, in Settings or
per run. Presets are defined only in `core/fetcher.py` (`SPEEDS`); every preset is at or above the 3 s floor,
and a test enforces it. There is no custom value field.

## 12. Updates and code signing

- Unsigned builds are blocked by Smart App Control / App Control for Business ("An Application Control
  policy has blocked this file", CreateProcess code 4551). Releases should be signed: `packaging/build.py`
  signs every unsigned .exe/.dll/.pyd and the installer and uninstaller when `GLEANER_SIGNTOOL_ARGS` is set
  (Microsoft Trusted Signing or an OV/EV certificate kept in the Windows certificate store). No certificate
  password or key file path with a password may be placed in the repository or in environment variables.

- The update check only reads version information (GitHub latest release or a `latest.json` manifest).
  Nothing is downloaded until the user clicks Update now (v0.9). The installer is then downloaded over https
  (or copied from the shared folder) and kept only if its SHA-256 matches the digest GitHub publishes for the
  release asset (or `sha256` in latest.json); an https installer without a published checksum is never run,
  the user gets the download link instead. Gleaner then starts that installer silently and closes; it
  never runs anything else it downloaded.
- Remote manifests and installer links must be https; shared-folder paths are allowed.
- The GitHub source must be a public repository. No token is ever stored in the app.
- Failures at start-up are silent; Check now shows a plain-language reason.
