# UX Flows

All messages shown to users are plain language. No stack traces, HTTP jargon or selector syntax in the
main UI (technical details go to a collapsible "Details" area and the log file).

## Flow 1 - Build a recipe (list page only)

1. User clicks **New Recipe** in the Library.
2. Dialog asks for a recipe name and start URL. User clicks **Open**.
3. App checks robots.txt for the URL.
   - Disallowed: message "This site asks robots not to collect this page. Gleaner won't collect
     it." The recipe cannot be saved.
4. Page loads in the built-in browser (left). Field panel on the right is empty.
5. User clicks **+ Add list field**. Cursor changes; hovering outlines elements.
6. User clicks an example (e.g. a business name).
7. App highlights every matching element and shows "15 items found on this page".
8. Panel shows a new field row: name box (focused), type dropdown (Text), Required checkbox.
9. If the match is wrong, user clicks another example of the same field: app recalculates.
   User can also click **Clear picks** on that field.
10. User repeats 5-9 for other fields.
11. Preview table (bottom) fills with up to 10 rows.
12. User clicks **Save**.

Success: Recipe appears in Library with "Never run".
Failure: Clicked element matches nothing repeated - message "This looks like a single item, not a list.
Pick it as a page field instead?" with Yes/No.

Loading State: Browser shows a spinner; field picking disabled until the page finishes loading.
Error State: Page fails to load - "Couldn't open this page. Check the address and your internet."
Empty State: Field panel shows "Click + Add list field, then click an example on the page."

## Flow 2 - Add pagination

1. In the builder, user clicks **Mark next page**.
2. User clicks the site's "Next" (or "2") link/button.
3. App follows it, checks the same fields match on page 2, and shows "Page 2 found - 15 items".
4. Pagination row in the panel shows a green tick.

Failure: Next page has no matching items - "Page 2 looks different. Try clicking the Next button
again." Pagination not saved.

## Flow 3 - Add detail page fields

1. User clicks **Mark item link** and clicks the link/button that opens one item's page.
2. App opens that item's detail page in the browser. Panel switches to a "Detail page" section.
3. User clicks **+ Add item field**, clicks a value on the page (e.g. the phone number next to
   "Phone Number"), names it, sets its type.
4. Where the page uses label/value rows, the field is found by its label (Found column shows
   "next to 'Phone Number'"), so it still works when rows shift between profiles.
5. User clicks **Back to list**. **Preview item pages** fills item columns for the first 3 rows
   (fetched politely).
6. User saves. Gleaner fetches the start page once without the browser. If far fewer items are found that
   way than the builder's browser shows (the site builds its list with JavaScript), the recipe is saved for
   browser runs: "Saved. This site builds its list with JavaScript, so runs open each page in Gleaner's
   browser: 15 items on this page, a little slower than usual." If neither way finds items: "No items found
   on the start page. Open the list page and check the preview." (not saved).

## Flow 4 - Run a recipe

1. User selects a recipe in the Library and clicks **Run**.
2. Run dialog: optional limits (max pages, max records). **Start**.
3. Run view shows: status, pages done, records collected, current page, elapsed, estimated time left,
   and a live log in plain language ("Collected record 41 (page 3)").
4. User can **Pause** (finishes the current request then waits), **Resume**, **Stop**.
5. When done: banner "Done - 1,240 records. 1,120 ready, 120 need review." with **Open Excel** and
   **Open folder**.

Loading State: Progress bar indeterminate until the first listing page is read.
Error State: see Flow 5 and Flow 6.
Empty State: "No items found on the start page. The site may have changed. Edit the recipe."

## Flow 5 - Site blocks the run

1. Runner detects a block signal.
2. Run stops at once. No retry.
3. Red banner: "The site stopped responding to us normally (it may have blocked this PC). The run has
   been stopped. Don't run this recipe again today. Tell your manager." **Details** shows the signal.
4. Excel is still written with what was collected.
5. Library shows a red "Blocked" badge on the recipe. Next Run asks: "Last run was blocked on <date>.
   Run anyway?" (default No).

## Flow 6 - Resume after interruption

1. App closed, crashed, or PC restarted mid-run.
2. User opens the app; Library shows the recipe with "Stopped - 640 records".
3. User clicks **Run**. App says "Continuing from where it stopped" and skips cached pages.

## Flow 7 - Export again

1. User selects a recipe and clicks **Export**.
2. App writes a new timestamped workbook from stored data (no network) and opens the folder.

## Flow 8 - Change theme, speed or folders

1. User opens **Settings**.
2. **Theme**: Match Windows / Light / Dark. Applies at once; Match Windows follows Windows when it switches.
   **Built-in browser**: "Block ads and trackers while building recipes" (on by default); applies to pages
   opened after the change (reload).
   The theme button at the bottom of the sidebar (any screen, Ctrl+Shift+T) cycles the same three; Settings
   follows it.
3. **Collection speed**: Gentle / Normal / Faster, each with its trade-off in one sentence. This is the
   default for new runs; the Run screen has a Speed box to change it for one run.
4. **Where your files are**: Excel folder (Change..., Open) and data folder (Open).

## Flow 9 - Learn to build a recipe

1. First start: Library shows "New to Gleaner? The 5-minute guide walks you through your first recipe."
   with **Open the guide** and **Hide**. Either choice stops the tip from showing again (Settings can bring
   it back).
2. **Guide** screen: chapter list on the left, chapter text on the right.
3. In the builder, the **Steps** box ticks off: open the list page, add a list field, (optional) next page,
   (optional) item link + item fields, save. **How does this work?** opens the tutorial chapter.

## Flow 10 - Update to a new version

1. Gleaner starts and quietly checks the update source (if enabled in Settings).
2. Newer version found: a small window "Gleaner 0.9.0 is available. You have 0.8.0." with the release notes,
   **Update now** / **Later** (it doesn't block the app), plus a Library banner with the same buttons.
   No message when there is no update or the PC is offline.
3. **Update now**: progress window "Downloading... 40 of 143 MB" with Cancel. The file is kept only if its
   SHA-256 matches the one published with the release; otherwise "The downloaded installer doesn't match the
   published version, so it was deleted. Try again later."
4. "Gleaner 0.9.0 is ready to install. Gleaner will close, update and open again (about a minute)." OK /
   Cancel. A running collection blocks this ("Stop the run, then click Update now again"); unsaved recipe
   changes are asked about first.
5. The installer runs silently, replaces the program, keeps recipes, data and Excel files, and starts Gleaner.
6. When Gleaner runs from source (developers) or the source gives no checksum, the button reads **Download**
   and opens the installer link instead.
7. **Settings > Updates > Check now** does the same on demand and explains problems in plain language.

## Flow 11 - Auto-detect

1. On a list page in the builder, user clicks **Auto-detect**.
2. Matching items light up; the Fields table fills with proposed columns ("auto-detected"), the item link
   and the next page are set when found. Message: "Found 15 items with 5 fields. Each item has its own
   page: click Open an item, then Auto-detect again there. Next page found."
3. If list fields already existed, the user is asked before they are replaced.
4. On an item page, Auto-detect adds every label/value pair not already picked.
5. Fields that look like date of birth, ID or bank details are not added; the message lists them.
6. Nothing found: "Couldn't find a repeating list on this page. Pick the fields by hand."

## Flow 12 - Start pages

1. Builder, list page: **+ Add this page** adds the current list to **Start pages**.
2. User browses to another list (another city) and adds it too; or **Paste addresses...** with one address
   per line (unusable lines are counted and skipped).
3. Save. Runs visit every start page; the log says "Start page 2 of 12".

## Flow 13 - Master list and sharing

1. Library > **Master list...**: dialog lists recipes with record counts (recipes with records ticked).
   **Create Excel** writes Master / Needs Review / Sources; banner offers Open Excel / Open folder.
2. Library > **Share recipe...**: save dialog for `<recipe>.json`; banner explains how a colleague imports it.

## Flow 14 - Heading list (headings with paragraphs)

1. Builder on a page where each entry is a heading followed by paragraphs. **Auto-detect**: List type
   switches to **Headings with text below**; headings light up; Fields: Name, Address, Email, Phone,
   Website. Message: "Found 40 headings with text below with 5 fields."
2. By hand: choose **List type > Headings with text below** (confirm if list fields exist: they are
   removed). **+ Add list field**, click a heading; then click a paragraph under it. A paragraph with
   "Email: / Phone:" lines adds one column per label: "Added columns for: Email, Phone."
3. Clicking outside any listed section: "That isn't inside one of the listed sections."
4. **Phone country** combo (India +91 default; Other... asks for a 1-3 digit code).

## Flow 15 - Browse back and forward in the builder

1. Back / Forward / Reload buttons left of the recipe name, Alt+Left / Alt+Right.
2. Back from an item page returns to list mode (list buttons enabled). Forward to the item page returns to
   item-page mode. Back is disabled on the first page.

## Flow 16 - Find & delete person

1. Library > **Find & delete person...**. Dialog: search box (phone, email or name; at least 3 characters).
2. Results: one row per record (ticked), with recipe and the record's values. "No collected records match.
   Nothing to delete." when empty.
3. **Delete and don't collect again** > confirm "Delete N records for good and add this person to the
   do-not-collect list? This can't be undone."
4. Library banner: "Deleted N records. They are on the do-not-collect list now." with the reminder that
   earlier Excel files must be cleaned by hand.
5. Later runs: log line "Skipped a record on the do-not-collect list." (no personal data).

## Flow 20 - Check a column on the page (v0.9)

1. Builder: click a column under Columns. Its values are outlined on the page; the page scrolls smoothly to the
   first one, which flashes. Instruction: "'Phone' is outlined on the page (22 found). The flashing one is the
   first." Nothing found: "'Phone' isn't on this page. Pick again to fix it, or Remove it."
2. Works for list columns, heading-list columns (label or position in the section) and item-page columns
   (by position or by label). A column of the other page type: "Open the item page to see where 'Phone' is."
3. Click a Preview row: the page scrolls to that item and outlines it (in heading lists: the heading and its
   paragraphs).

## Flow 19 - Recipe builder layout (v0.8)

1. Top: browser bar with Back / Forward / Reload, the address and **Open**. The address shows the page in the
   browser.
2. Left: the website. Right: a panel with the recipe name, one instruction line, and three step tabs
   (**List**, **Item page**, **More pages**) that tick when done.
3. List step: Auto-detect, + Add field, Mark item link. Item page step: Open an item; once on an item page,
   Auto-detect, + Add field, Back to list. The builder switches to the Item page step on an item page and
   back to List on the list.
4. More pages step: Mark next page and start pages.
5. Columns of the current step below (name, type, required; "found" as a tooltip), with Pick again / Remove.
6. Options (closed): list type, phone country. Bottom: How does this work? and Save recipe.
7. Bottom: Preview, foldable.

## Flow 17 - Sidebar and theme button

1. Sidebar top: menu button (Ctrl+B) collapses the sidebar to icons (52 px); each icon shows its section name
   as a tooltip; the choice is remembered.
2. Sidebar bottom: "Theme: Light" button with sun / moon / monitor icon; click (or Ctrl+Shift+T) cycles
   Match Windows > Light > Dark; status bar shows "Theme: Dark" for 3 s.

## Flow 18 - Run a JavaScript site

1. Recipe saved for browser runs (Flow 3 step 6).
2. Run looks the same; each page opens in a hidden browser tab (pictures off), waits until the list shows
   (or the page stops changing, at most 20 s), then is read like any other page.
3. A browser that can't open the page within about a minute counts as a network problem (retried, then
   "Network problem. Run again to continue.").
