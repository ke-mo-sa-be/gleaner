# Product Requirements Document

Status: Draft v2 (2026-10-14). Items marked **ASSUMPTION** or listed under Open Questions are not yet
confirmed by the business owner.

## 1. Product Overview

Product Name: Gleaner
One-Line Description: A Windows desktop app that lets a non-technical person point and click on any
directory-style website to collect its listings into a clean Excel file.
Product Type: General-purpose desktop tool (first used by a marketing data team)
Primary Platform: Desktop (Windows 10/11 only)

## 2. Problem

What problem are we solving?
Teams that need lists from the web (businesses, shops, suppliers, products, members, professionals such
as doctors or lawyers) copy them by hand from directory websites. These sites usually have several layers
(region > city > category > listing > item page), each with many pages.

Why does this problem matter?
- Manual copying is slow: a few hundred records per person per day.
- Copying by hand introduces typos, duplicates and inconsistent formats.
- Generic scraping tools either need programming skills or behave aggressively and get users blocked.

How are users solving this today?
Manual copy-paste into Excel. A command-line MVP (`scraper/`, one directory only) proved the approach:
20 records in ~3.5 minutes, cleaned and exported to Excel.

First use case: a marketing data team collecting healthcare contacts (hospitals, clinics, doctors,
procurement and admin staff). Nothing in the product is specific to that domain.

## 3. Goal

Primary Goal: Anyone comfortable with a browser and Excel can set up and run collection from a new
directory-style site without writing code, and get a clean, deduplicated Excel file.

Secondary Goals:
- Raise throughput to 3,000+ records per PC per working day.
- Cut field errors (bad phones, duplicates) below manual levels.
- Never get the user blocked: the app always behaves politely and stops when a site objects.

## 4. Target Users

### User Type 1
Name: Data Executive
Description: Data entry / research staff. Comfortable with a browser and Excel, not with code or terminals.
Needs:
- Run an existing recipe with one click and get Excel.
- Understand why a run stopped, in plain language.
Pain Points:
- Repetitive clicking through layers of pages.
- Getting blamed for typos and duplicates.

### User Type 2
Name: Recipe Builder
Description: Team lead or senior executive who sets up a new site once so others can run it.
Needs:
- Teach the app which items and fields to collect by clicking on the page.
- See a live preview to confirm it picked the right things.
Pain Points:
- Every site has a different layout.

### User Type 3
Name: Owner
Description: Manager responsible for the data and for compliance.
Needs:
- Know which sites were collected, when, and how many records.
- Confidence the tool will not cause bans or legal trouble.

## 5. User Stories

- As a Recipe Builder, I want to open a website inside the app so that I can teach it what to collect.
- As a Recipe Builder, I want to click one example and have all similar items highlighted so that I do
  not have to select each one.
- As a Recipe Builder, I want to name each field (Name, Phone, Address) so that Excel columns are clear.
- As a Recipe Builder, I want to mark the "Next" button so that the app goes through every page.
- As a Recipe Builder, I want to mark the link to a detail page and pick fields there so that inner-page
  data is collected too.
- As a Recipe Builder, I want a live preview table so that I can check the result before saving.
- As a Data Executive, I want to pick a saved recipe and press Run so that collection starts.
- As a Data Executive, I want to pause, resume and stop a run so that I control my PC's work.
- As a Data Executive, I want a run to continue where it stopped after a crash or restart.
- As a Data Executive, I want a plain message when a site blocks us so that I know to stop and report it.
- As an Owner, I want each Excel to include a Run Log so that I can audit what was collected.

## 6. Core Features

### Feature 1 - Recipe Builder
Purpose: Teach the app what to collect from one site, without code.
User Flow: New Recipe > enter start URL > page loads in built-in browser > "Add list field" >
click an example > similar items highlight > name the field and choose its type > repeat > "Mark next
page" > click the Next control > (optional) "Mark detail link" > click a link > app opens a sample
detail page > pick detail fields > preview > Save.
Inputs: Start URL, clicks on page elements, field names, field types.
Outputs: A saved recipe (JSON) in the recipe library.
Acceptance Criteria:
- Clicking one element in a repeated list highlights all matching elements on the page and shows the
  match count.
- A second click on another example of the same field narrows or widens the match correctly.
- Field types: Text, Link (URL), Phone, Email, Pincode, Number. Type controls cleanup in export.
- Preview shows the first 10 rows with all list fields, plus detail fields for the first 3 rows.
- Marking pagination supports a "Next" link/button and numbered page links.
- One level of detail pages is supported.
- A recipe can be saved, reopened, edited and duplicated.
- Builder tells the user if robots.txt disallows the start URL, and will not save a recipe for it.
Edge Cases:
- Clicked element is not part of a repeated list (single field on page, e.g. page title).
- Page content appears only after JavaScript runs.
- Page needs scrolling or a "Load more" button to show more items.
- Field missing on some items (must produce an empty cell, not shift columns).
- Site changes layout after a recipe was saved (run reports 0 matches and stops).

### Feature 2 - Runner
Purpose: Execute a recipe safely and resumably.
User Flow: Library > select recipe > Run > progress view (pages, records, current URL, elapsed, ETA) >
Pause / Resume / Stop > finished banner with "Open Excel".
Acceptance Criteria:
- One request at a time; random pause between requests chosen by speed: Gentle 10-20 s, Normal 5-10 s
  (default), Faster 3-5 s. The 3 s minimum cannot be changed by users.
- robots.txt checked before the first request to each host; disallowed URLs stop the run.
- Block signals (HTTP 401/403/429/503, Cloudflare challenge/ban page, CAPTCHA page, 3 blank pages in a
  row) stop the run immediately with a plain-language message.
- Every fetched page cached; a re-run never refetches cached pages and resumes where it stopped.
- Optional limits: max pages, max records.
- The app stays responsive during a run.
Edge Cases:
- PC sleeps or network drops mid-run.
- App closed during a run (must resume on next Run).
- Pagination loops back to page 1 or repeats a page (must stop, not loop forever).

### Feature 3 - Clean & Export
Purpose: Turn raw collected values into a usable Excel file.
User Flow: Automatic at end of every run, or "Export" button in the library.
Acceptance Criteria:
- Workbook sheets: Records, Needs Review, Run Log.
- Phone fields normalised to `+91XXXXXXXXXX` (multiple numbers comma-separated); invalid ones flagged.
- Email fields lower-cased and syntax-checked; Pincode fields extracted as 6 digits.
- Duplicate rows (by the recipe's chosen key fields) moved to Needs Review with "duplicate of <ID>".
- Rows missing any field the recipe marks as Required go to Needs Review with the reason.
- Columns: Record ID, recipe fields in recipe order, Source URL, Collected On, Issues.
Edge Cases:
- Recipe has zero records (still writes workbook with Run Log).
- Excel file already open in Excel (write to a new timestamped name, never crash).

### Feature 4 - Recipe Library
Purpose: Find, run and manage recipes.
Acceptance Criteria:
- List shows name, site, record count, last run date and last run status.
- Actions: Run, Edit, Duplicate, Export, Delete (with confirmation; deleting a recipe keeps exported
  Excel files).
- A recipe whose last run ended "Blocked" shows a red badge and asks for confirmation before running.

### Feature 5 - Settings
Purpose: Let each user adjust the app without touching files.
Acceptance Criteria:
- Theme: Match Windows (default, follows Windows light/dark live), Light, Dark.
- Default collection speed (Gentle / Normal / Faster) with plain-language trade-offs; the Run screen can
  override it for one run.
- Excel output folder (default Documents\Gleaner) and the data folder, each with an Open button.
- Updates: check automatically at start (on by default), update source, Check now.
- Help: open the guide, show the welcome tip again. About: version.
- Stored in `<data folder>\settings.ini`.

### Feature 6 - Guide and tutorial
Purpose: Users learn recipes (including multi-layer sites) without asking someone.
Acceptance Criteria:
- Guide screen with chapters: getting started, the three kinds of page, step-by-step tutorial,
  directories with many layers, running, speed, the Excel file, blocks, updates, troubleshooting.
- Source is docs/USER_GUIDE.md, bundled with the installer.
- Library shows a dismissable "New to Gleaner?" tip until the user opens or hides it.
- Builder shows a live step checklist and a "How does this work?" link to the tutorial chapter.

### Feature 7 - Updates
Purpose: Get new versions to users without anyone sending files around.
Acceptance Criteria:
- Source is either `github:owner/repo` (latest public GitHub release with a Setup .exe asset) or a
  `latest.json` manifest in a shared folder or at an https address.
- Check is read-only; the user decides to download. Installing over an existing install keeps recipes,
  data and Excel files.
- Offline or unreachable source at start-up is silent; Check now explains the problem.

## 7. Non-Goals

The following are intentionally NOT part of this version:
- Solving CAPTCHAs, rotating IPs, proxies/VPN integration, or any other way around a site's block.
- Automating logins or storing website passwords (a user may sign in by hand inside the app's browser).
- Extracting data from images or PDFs.
- Submitting contact forms to reveal hidden contact details.
- Scheduling, multi-user/server deployment, cloud sync.
- macOS or Linux.
- Sending marketing messages.

## 8. MVP Scope

Must Have:
- Feature 1 with list fields, pagination (Next link/button), one detail level.
- Feature 2, Feature 3, Feature 4.
- Windows installer (no Python needed on user PCs).
- The first directory MVP re-created as a recipe and matching the CLI's output.
- Settings (theme, speed, folders, updates), in-app guide, update check (added in v0.4).

Nice to Have:
- "Load more" button and infinite scroll pagination.
- In-app sign-in session kept between runs for sites the team has accounts on.
- Pincode fill-in from district/area when missing.

Future:
- AI "Auto-detect fields" (proposes fields from a page; user confirms).
- AI extraction fallback for pages with irregular layouts.
- Several start pages per recipe (one recipe covering many cities/categories).
- Multiple detail levels; region > city > category drill-down recipes.
- Scheduled runs; silent auto-update; code-signed installer.

## 9. Success Metrics

Primary Metrics:
- A Data Executive builds a working recipe for a new directory site in 15 minutes or less, with at most
  one question to the Recipe Builder (measured in UAT with 3 sites).
- 3,000+ records per PC per 8-hour day on a typical directory.

Secondary Metrics:
- Field error rate under 2% on a 50-row spot check against the website.
- Zero runs that continue after a block signal.

## 10. Constraints

Technical: Windows 10/11 only. Runs without admin rights. Python 3.12+ codebase; shipped as a bundled
executable. All data stays on the local PC.
Business: No paid SaaS dependencies for the MVP. AI features optional and off by default.
Design: Usable by people who have never used a terminal. Plain-language messages only.
Timeline: ~5 weeks to UAT (Builder 2 wk, Runner 1 wk, Export/Library + installer 1 wk, UAT 1 wk).

## 11. Assumptions

- **ASSUMPTION:** Target sites are mostly server-rendered directory sites (tables, lists, cards) like
  drdata.in. Heavy JavaScript apps are supported by the built-in browser renderer but are slower.
- **ASSUMPTION:** One detail level covers most needs (list > profile).
- **ASSUMPTION:** Each PC runs one recipe at a time.
- **ASSUMPTION:** Exported data is used only for B2B outreach to healthcare professionals, with DND
  scrubbing and opt-out handled by the marketing team (see SECURITY.md).

## 12. Open Questions

- Which 3-4 sites (besides drdata.in) should UAT use? Each must not have blocked the company.
- Does marketing need a fixed Excel column template, or are recipe-defined columns fine?
- Is a code-signing certificate wanted (removes Windows "unknown publisher" warning; ~Rs 15-25k/yr)?
- Should new sites need Owner approval before first run?
- Where should exported Excel files go by default (Documents\Gleaner, a shared drive)?

## 13. Definition of Done

The feature/product is complete when:
- [ ] Requirements are implemented
- [ ] Critical user flows work (UX_FLOWS.md)
- [ ] Tests pass
- [ ] Build (installer) succeeds
- [ ] Security requirements are satisfied (SECURITY.md)
- [ ] Documentation is updated
