"""drdata.in doctor directory: public listing pages and public profile pages.

Layout (checked Oct 2026):
  listing  list-doctors.php?search=Doctor&specialization=<X>&page=<N>
           table under #no-more-tables, 15 rows per page, cells keyed by data-title
  profile  /<slug>, two-column table under #profile (label | value)

The state/city filters on the site currently return 0 rows, so the crawl goes
by specialization and keeps state/city from each row.
"""

from urllib.parse import quote, urlencode, urljoin

from bs4 import BeautifulSoup

SOURCE = "drdata.in"
BASE = "https://www.drdata.in/"
LISTING = BASE + "list-doctors.php"

# Profile label -> our field. Date of Birth and the free-text "About" section
# exist on the page but are deliberately not collected: not needed for outreach.
PROFILE_FIELDS = {
    "Name": "name",
    "Specialization": "specialization",
    "Degree": "degree",
    "Area of Practice": "area_of_practice",
    "Practicing Since": "practicing_since",
    "Name of Medical Council": "medical_council",
    "Registration Number": "registration_number",
    "Clinic/ Hospital Name": "facility_name",
    "Address": "address",
    "State": "state",
    "District": "district",
    "Geographical Area": "area",
    "Phone Number": "phone",
}

LISTING_CELLS = {"Name": "name", "Special.": "specialization", "Degree": "degree", "State": "state", "City": "city"}

EMPTY = {"", "--", "-", "NA", "N/A"}


def _clean(text):
    text = " ".join(text.split())
    return None if text in EMPTY else text


def listing_url(specialization, page):
    return LISTING + "?" + urlencode({"search": "Doctor", "specialization": specialization, "page": page}, quote_via=quote)


def parse_specializations(html):
    soup = BeautifulSoup(html, "html.parser")
    return [o["value"] for o in soup.select("select#specialization option") if o.get("value")]


def parse_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("#no-more-tables tbody tr"):
        link = tr.select_one("a[href]")
        if not link:
            continue
        row = {"profile_url": urljoin(BASE, link["href"])}
        for td in tr.find_all("td"):
            key = LISTING_CELLS.get(td.get("data-title", ""))
            if key:
                row[key] = _clean(td.get_text(" "))
        rows.append(row)
    return rows


def parse_profile(html):
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for tr in soup.select("#profile table tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        key = PROFILE_FIELDS.get(" ".join(tds[0].get_text(" ").split()))
        if key:
            out[key] = _clean(tds[1].get_text(" "))
    return out
