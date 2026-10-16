# Gleaner user guide

## Getting started

**Finding your way around.** The menu on the left switches between Library, Recipe builder, Run, Guide and
Settings. The three-line button at its top hides the names to give the screen more room (Ctrl+B); point at an
icon to see its name. The button at the bottom switches the theme: Match Windows, Light, Dark (Ctrl+Shift+T).

Gleaner collects lists from websites into a clean Excel file: businesses in a directory, shops in a
city, products in a catalogue, members of an association, doctors or hospitals in a medical directory,
anything that a website shows as a repeating list.

You teach Gleaner **once** per website by clicking on the page. That saved set of clicks is called a
**recipe**. After that, anyone can press **Run** and get the Excel file.

The usual day looks like this:

1. **Library**: pick a recipe and press **Run**.
2. **Run**: watch it work. You can pause, stop, and continue later.
3. Open the Excel file it made.

Making a new recipe takes about 10-15 minutes the first time, often less with **Auto-detect**. The next
chapters show how, step by step.

## The three kinds of page

Almost every directory website is built from three kinds of page. The Recipe builder has one step (a tab
on the right) for each: **List**, **Item page** and **More pages**. A tick appears on a step when it is done.

**1. The list page.** Many items one under the other: a table, cards or a list. Each item shows a few
details (a name, a city) and often a link such as "View details".
Step **List**: **Auto-detect**, **+ Add field**, **Mark item link**.

**2. The item page.** What opens when you click one item. It shows the full details of that one item:
phone, address, email.
Step **Item page**: **Open an item**, then **Auto-detect** or **+ Add field** there.

**3. More pages of the list.** "Next", "2 3 4 ...", "Older results" at the bottom of the list.
Step **More pages**: **Mark next page**, and start pages.

You only need what your website has. A site that shows everything on the list page needs no item page.
A site with one short list needs no next page.

## Tutorial: your first recipe

Follow along with any directory website. The example uses a list of shops, but the steps are the same
for any site.

**Step 1 - Open the list page**

1. Go to **Recipe builder** (or **Library > New recipe**).
2. Type the website address in the address bar at the top and press **Open**.
3. In the built-in browser, go to the list you want. Use the site's own search boxes and filters (city,
   category) as you normally would, until you see the list of items you want.

Tip: what you see now is where every run will start. If you want shops in Pune only, filter to Pune first.

Gleaner's browser removes ads and pop-up ads from the pages you open, so lists are easier to see and click.
The page itself is never changed. If a site refuses to work ("please disable your ad blocker"), turn off
**Settings > Built-in browser > Block ads and trackers** and reload the page.

The arrows left of the address work like a web browser's: **Back** and **Forward** (or Alt+Left /
Alt+Right) and **Reload**. Going back from an item page returns you to the list page.

**Step 2 - Pick the values you want from the list**

Quickest way: click **Auto-detect**. Gleaner finds the repeating list, proposes its fields with column
names, finds the link to each item's own page and the next-page link. Check the **Preview** at the bottom,
remove columns you don't need (select one, **Remove**) and rename columns. Anything that looks like a date
of birth, ID or bank detail is left out automatically.

If Auto-detect picks the wrong list or misses a value, pick by hand:

1. On the **List** step, click **+ Add field**. The mouse becomes a cross.
2. Click on one shop's **name**. Every shop's name lights up in orange, and the column appears under
   **Columns** (point at it to see "15 of 15 items" or similar).
3. Double-click the column's name and rename it, for example "Shop name".
4. Repeat for other values on the list page: city, category, phone if it is shown.

**Check a column on the page.** Click a column under **Columns**: every value it finds is outlined, the page
scrolls to the first one and it flashes, so you can see exactly what Gleaner will collect. Click a row in the
**Preview** to jump to that item on the page.

If some items light up wrongly or are missing, select the column, click **Pick again** and
click the same value on a **different** item. Gleaner combines both examples.

The **Preview** at the bottom shows the first 10 rows exactly as they will appear in Excel.

**Pictures.** Click a picture (a logo, a photo of a product or doctor) with **+ Add field** and Gleaner
makes an **Image** column with the picture's web address. Open the address to see the picture. The
picture itself is not downloaded into Excel. You can also switch any column to type **Image** in the
**Type** column.

**Step 3 - Item pages (if the list doesn't show everything)**

1. On the **List** step, click **Mark item link**, then click the link or button that opens one shop
   ("View", "Details", the shop's name, ...).
2. Gleaner opens that shop's page and switches to the **Item page** step. Click **Auto-detect**: it
   proposes every "label: value" pair on the page (Phone, Address, Email, ...). Or click **+ Add field**
   and click a value, for example the phone number.
3. If the page shows details as label and value ("Phone: 98450 00000"), pointing at the column shows
   "next to 'Phone'". That is good: it will work for every shop even if their pages are laid out a little
   differently.
4. Add the other values you need (address, email, ...). Rename the columns.
5. Click **Back to list**. Click **Preview item pages** (above the preview) to check the first 3 items
   (takes about 30 seconds, because Gleaner fetches them politely).

**Step 4 - More pages (if the list continues)**

1. On the list page, open the **More pages** step and click **Mark next page**.
2. Click the site's **Next** button, or the link to page **2**.
3. Next to the button you will see how Gleaner will move: "by page number" or "the 'Next' link".

**Step 5 - Save**

1. Give the recipe a clear name at the top of the right-hand panel, e.g. "Shops - Pune - Electronics".
2. Click **Save recipe**. Gleaner reads the first page once, the way a run will, to make sure it works.
3. Go to the **Library** and press **Run**.

The **Preview** at the bottom can be folded away with its arrow when you need more room. Rarely used
settings (**List type**, **Phone country**) are under **Options**, near **Save recipe**.

## Lists written as headings and paragraphs

Some websites, often blog-style articles such as "Top medical equipment suppliers in Nigeria", don't
have a list or table. Each entry is a **heading** (the company name) followed by a few **paragraphs**
(the address, then lines like "Email: ..." and "Phone: ...").

**Auto-detect** recognises this and sets **List type** (under **Options**) to **Headings with text below**. It proposes
**Name** (the heading), **Address** (the first plain paragraph), one column per label that most
entries have (**Email**, **Phone**, ...) and **Website** if entries show a web address. Check the preview.

To pick by hand:

1. Open **Options** and set **List type** to **Headings with text below**.
2. Click **+ Add field** and click one entry's **heading**. Every heading of the list lights up.
3. Click **+ Add field** again and click the address paragraph under a heading.
4. Click **+ Add field** and click the paragraph with "Email: ... Phone: ...". Gleaner adds one
   column per label it finds there. Remove the ones you don't need.

Different words for the same thing go into one column: "Phone:", "Tel:" and "Telephone:" all fill **Phone**;
"Mobile:"/"Cell:", "Fax:", "Email:"/"E-mail:" and "Website:"/"Web:" get their own columns. When a value
continues on the next line (a second phone number or email under the first), both are kept in the same cell.
Emails written as name[at]site.com are cleaned to name@site.com in Excel.

Gleaner ignores side bars, "related posts" boxes and comments when it looks for the list. If you set **List
type** to **Headings with text below** yourself, Auto-detect only looks for that.

## Phone numbers from other countries

Phone numbers are written in Excel with their country code, for example +919845000000. Numbers that
already start with + (or 00) keep their own country code. For numbers written without one, Gleaner uses
the recipe's **Phone country** (in the builder, under **Options**): India +91 unless you choose
another, for example Nigeria +234 for a Nigerian directory. A leading 0 is dropped (0803 ... becomes
+234803...). Choose **Other...** to type any country code.

## Directories with many layers

Some websites make you go through several layers before you reach a list, for example:

> State > City > Category > list of shops > one shop's page

Gleaner follows **two** of those layers automatically: the **list** (with all its pages) and each
**item page**. For the layers above the list (state, city, category) use **start pages**: one recipe that
starts at several lists.

1. In the builder, click through the site's layers yourself (choose the state, then the city, then the
   category) until you see the list. Build the recipe there (Steps 2-5 above).
2. On the **More pages** step, under start pages, click **+ Add this page**.
3. In the built-in browser, go to the next city's (or category's) list and click **+ Add this page**
   again. Repeat for every list you want.
4. Or click **Paste addresses...** and paste many list addresses at once, one per line. Handy when the
   address only changes in one place, for example `...?city=Pune`, `...?city=Mumbai`, `...?city=Delhi`.
5. **Save recipe**. A run goes through every start page, with all their pages and item pages.

The Excel file has a **Start Page** column, so you can see which city or category each row came from.

If you prefer separate files per city, you can still **Duplicate** a recipe (Library, **More**) and change its
start page.

Many sites also have one long list of everything (for example "All shops") with a filter on the side.
That single list is often the quickest recipe: one recipe instead of one per city.

## Running a recipe

1. **Library**: select the recipe, click **Run**.
2. Optional: **Stop after** a number of records or pages. Good for a first test (e.g. 20 records).
3. Choose the **Speed** (see the next chapter) and press **Start**.

While it runs you can **Pause**, **Resume** or **Stop**. Closing Gleaner or a power cut is also fine:
press **Start** again later and it continues where it stopped. Pages it already read are never read again.

## Speed

Gleaner waits between pages on purpose. Fast, non-stop requests are how websites spot and block robots,
and they can slow the website down for everyone else.

- **Gentle**: 10-20 seconds between pages (about 240 pages an hour). Use for small sites, or a site that
  blocked you before.
- **Normal**: 5-10 seconds (about 480 pages an hour). Recommended.
- **Faster**: 3-5 seconds (about 900 pages an hour). Higher chance of being blocked.

Gleaner never goes faster than one page every 3 seconds. Set the default in **Settings**; change it for
one run on the **Run** screen.

A page here means one list page or one item page. A recipe with item pages reads one page per item.

## Your Excel file

Every run writes a new Excel file (older files are never overwritten). It has three sheets:

- **Records**: the rows ready to use. Phone numbers are written with their country code (+91XXXXXXXXXX for
  India), emails in lower case, pincodes as 6 digits.
- **Needs Review**: rows with a problem, for example a required field is missing or the row is a
  duplicate of an earlier one. The **Issues** column says what is wrong.
- **Run Log**: when each run happened and how it ended.

Mark a field as **Required** in the builder if a row is useless without it (often the phone number).

## One master list from several recipes

**Library > Master list...** combines the results of the recipes you tick into one Excel file:

- **Master**: every row once, with a **Recipe** column saying where it came from.
- **Needs Review**: rows with problems, and rows whose phone number (or email, when there is no phone)
  already appeared in another recipe ("duplicate of Shops Pune R-00012").
- **Sources**: how many rows each recipe contributed and when it last ran.

## Sharing recipes with colleagues

Select a recipe in the **Library** and click **More > Share recipe...** to save it as a small file. Send the file
(email, chat, shared folder). Your colleague clicks **Import recipe...** in their Library. Only the recipe is
shared, never the collected data.

Excel files go to **Documents\Gleaner** unless you choose another folder in **Settings**.

## When a site says no

Gleaner stops by itself when:

- the site's robots rules say robots should not collect that page,
- the site refuses, challenges (an "are you human?" page) or starts sending empty pages.

It never tries to get around this. If a run says the site **blocked** this PC, don't run that recipe again
the same day and tell your manager. Running again can turn a short block into a long ban.

Some sites build their list with JavaScript inside the browser: the page arrives empty and fills in a moment
later. Gleaner notices this when you save the recipe and says so. Runs then open each page in Gleaner's own
browser (without pictures) and wait for the list to appear. That is a little slower, and the same speed,
robots and block rules apply.

Gleaner still can't collect:

- documents shown in a viewer (Scribd, PDF or slide viewers): the text is a picture of a page, not a list,
- lists that only grow when you scroll down or press **Load more**,
- sites that need you to sign in each time, or show an "are you human?" check.

## Removing a person (do-not-collect list)

When someone asks to be removed from your lists:

1. **Library > Find & delete person...**
2. Type their phone number (any format), email or name and press **Search**. Gleaner searches the records
   of every recipe.
3. Untick any records that are not this person, then click **Delete and don't collect again**.

Their records are deleted for good, and Gleaner remembers them on a **do-not-collect list**: later runs
skip them without even opening their page. The list keeps only a scrambled fingerprint (a hash) of their
phone number and email, not the numbers themselves.

Excel files you exported **before** the deletion still contain the person. Delete or edit those files by
hand, and tell colleagues who have copies.

## Updates

When Gleaner starts it checks for a new version and, if there is one, says so in a small window. Click
**Update now**: Gleaner downloads the new version (you see the progress), checks that it is the genuine file,
then closes, updates and opens again by itself, in about a minute. Your recipes, collected data and Excel files
are kept. **Later** keeps working; the Library shows the update until you install it.

You can also look yourself: **Settings > Updates > Check now**. If a collection run is going, stop it (or let it
finish) before updating.

## Questions and fixes

**The wrong things light up when I pick a field.** Select the column, **Pick again**, click the same value
on another item. If it is still wrong, remove the field and click a more specific spot (the text itself,
not the space around it).

**The preview shows empty cells for some rows.** Those items don't have that value on the site. If they
should, use **Pick again** on one of the empty ones.

**Item page values are empty for some items.** Open one of those items with **Open an item**, check where
the value is on that page, and **Pick again**.

**The run found 0 items.** The site may have changed its layout. **Edit** the recipe, check the preview,
and pick the fields again.

**Where are my recipes and data?** **Settings > Where your files are**.

**Installing on another PC says "An Application Control policy has blocked this file".** Windows Smart
App Control (or a company policy) only runs programs signed with a publisher certificate, and this copy
of Gleaner isn't signed yet. On a company PC, ask IT to allow Gleaner. On a home PC, wait for a signed
version rather than turning Smart App Control off: once off, Windows can't turn it back on without a reset.

**Personal data.** If you collect people's names and numbers, treat the Excel file as confidential: keep it
on your PC, check numbers against the DND list before calling or texting, include an opt-out, and delete a
person's details when they ask (**Library > Find & delete person...**).
