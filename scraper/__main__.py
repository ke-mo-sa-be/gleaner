"""CLI.

  py -m scraper drdata --specialization Radiologist --max-pages 2
  py -m scraper drdata --specialization all
  py -m scraper drdata --export-only
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .export import export_workbook
from core.fetcher import BlockedError, DisallowedError, EmptyPageError, Fetcher
from .sites import drdata
from .store import Store
from .validate import build_rows

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "scraper.db"
OUTPUT_DIR = ROOT / "output"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LeadCollector/0.1"


def log(msg):
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


MAX_CONSECUTIVE_EMPTY = 3


def crawl_drdata(fetcher, store, specializations, max_pages, max_profiles):
    """Walk listing pages per specialization, then each new profile. Returns (listing_pages, profiles)."""
    listing_pages = profiles = consecutive_empty = 0

    def fetch(url):
        # Blank pages are skipped (a re-run retries them); several in a row look like a soft block.
        nonlocal consecutive_empty
        try:
            html = fetcher.get(url)
        except EmptyPageError:
            consecutive_empty += 1
            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                raise BlockedError(f"{consecutive_empty} blank pages in a row, last {url}")
            log(f"  blank page, skipped: {url}")
            return None
        consecutive_empty = 0
        return html

    for spec in specializations:
        log(f"[{spec}] start")
        previous_first = None
        page = 1
        while not max_pages or page <= max_pages:
            html = fetch(drdata.listing_url(spec, page))
            if html is None:
                log(f"[{spec}] listing page {page} blank, moving to next specialization")
                break
            rows = drdata.parse_listing(html)
            listing_pages += 1
            # Past the last page the site returns no rows or repeats a page.
            if not rows or rows[0]["profile_url"] == previous_first:
                break
            previous_first = rows[0]["profile_url"]
            log(f"[{spec}] page {page}: {len(rows)} rows")

            for row in rows:
                if max_profiles and profiles >= max_profiles:
                    log(f"profile limit {max_profiles} reached")
                    return listing_pages, profiles
                url = row["profile_url"]
                if store.has_record(url):
                    continue
                html = fetch(url)
                if html is None:
                    continue
                profile = drdata.parse_profile(html)
                store.save_record(drdata.SOURCE, url, {**row, "source": drdata.SOURCE, "profile": profile})
                profiles += 1
                log(f"  + {profile.get('name') or row.get('name')}  ({profiles})")
            page += 1
    return listing_pages, profiles


def export(store, source):
    contacts, review = build_rows(store.records(source))
    path = OUTPUT_DIR / f"{source.split('.')[0]}_{datetime.now():%Y%m%d_%H%M}.xlsx"
    export_workbook(path, contacts, review, store.runs(source))
    log(f"Excel written: {path}  (contacts {len(contacts)}, needs review {len(review)})")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="scraper", description="Polite medical-directory collector")
    ap.add_argument("site", choices=["drdata"])
    ap.add_argument("--specialization", action="append",
                    help="Specialization as shown on the site (repeatable), or 'all'")
    ap.add_argument("--max-pages", type=int, default=0, help="Listing pages per specialization (0 = no limit)")
    ap.add_argument("--max-profiles", type=int, default=0, help="Stop after this many new profiles (0 = no limit)")
    ap.add_argument("--min-delay", type=float, default=5.0, help="Seconds between requests, lower bound (floor 3)")
    ap.add_argument("--max-delay", type=float, default=10.0, help="Seconds between requests, upper bound")
    ap.add_argument("--export-only", action="store_true", help="Skip crawling, just write Excel from stored data")
    args = ap.parse_args(argv)

    store = Store(DB_PATH)
    source = drdata.SOURCE

    if args.export_only:
        export(store, source)
        return 0
    if not args.specialization:
        ap.error("--specialization is required unless --export-only")

    fetcher = Fetcher(store, USER_AGENT, args.min_delay, args.max_delay, log=log)
    run_id = store.start_run(source)
    status, note, listing_pages, profiles = "done", "", 0, 0
    try:
        specs = args.specialization
        if "all" in (s.lower() for s in specs):
            specs = drdata.parse_specializations(fetcher.get(drdata.LISTING))
            log(f"{len(specs)} specializations found")
        listing_pages, profiles = crawl_drdata(fetcher, store, specs, args.max_pages, args.max_profiles)
    except BlockedError as exc:
        status, note = "blocked", str(exc)
        log(f"STOPPED - site sent a block signal: {exc}. Do not re-run against this source until reviewed.")
    except DisallowedError as exc:
        status, note = "disallowed", f"robots.txt disallows {exc}"
        log(f"STOPPED - {note}")
    except KeyboardInterrupt:
        status, note = "stopped", "stopped by user"
        log("Stopped by user. Progress is saved; re-run the same command to resume.")
    finally:
        store.finish_run(run_id, status, fetcher.requests_made, listing_pages, profiles, note)
        log(f"Run {run_id}: {status}, {fetcher.requests_made} requests, {profiles} new profiles")

    export(store, source)
    return 0 if status == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
