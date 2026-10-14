"""Command line for the core engine (until the desktop app ships).

  py -m core import recipes/drdata.json
  py -m core list
  py -m core run "drdata.in doctors" --max-records 20
  py -m core export "drdata.in doctors"
"""

import argparse
import logging
import sys

from core import paths
from core.export import export_workbook
from core.fetcher import Fetcher
from core.recipe import RecipeError, load_recipe
from core.runner import run_recipe
from core.store import Store

STATUS_TEXT = {
    "done": "Finished.",
    "stopped": "Stopped. Run again to continue.",
    "blocked": "STOPPED: the site sent a block signal. Do not run this recipe again until someone has reviewed why.",
    "disallowed": "STOPPED: the site's robots.txt does not allow collecting this page.",
    "network_error": "STOPPED: network problem. Run again to continue.",
    "no_items": "No items found on the start page. The site may have changed; edit the recipe.",
}


def _recipe_id(store, name):
    recipe_id = store.find_recipe(name)
    if recipe_id is None:
        sys.exit(f"No recipe named {name!r}. Use: py -m core list")
    return recipe_id


def _export(store, recipe_id):
    path, ready, review = export_workbook(
        paths.exports_dir(), store.get_recipe(recipe_id), store.records(recipe_id), store.runs(recipe_id)
    )
    print(f"Excel written: {path}  ({ready} ready, {review} need review)")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="core", description="Gleaner engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("import", help="Add or update a recipe from a JSON file")
    p.add_argument("file")
    sub.add_parser("list", help="List recipes")
    p = sub.add_parser("run", help="Run a recipe")
    p.add_argument("name")
    p.add_argument("--max-pages", type=int, default=0)
    p.add_argument("--max-records", type=int, default=0)
    p = sub.add_parser("export", help="Write Excel from stored records")
    p.add_argument("name")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    store = Store(paths.db_path())
    store.mark_interrupted()

    if args.cmd == "import":
        try:
            recipe = load_recipe(args.file)
            recipe_id = store.save_recipe(recipe, store.find_recipe(recipe.name))
        except RecipeError as exc:
            sys.exit("Recipe problems:\n  " + "\n  ".join(exc.problems))
        print(f"Saved recipe {recipe.name!r} (id {recipe_id})")
    elif args.cmd == "list":
        for r in store.list_recipes():
            print(f"{r['name']:<35} records {r['record_count']:>6}   last run {r['last_status'] or 'never'}")
    elif args.cmd == "run":
        recipe_id = _recipe_id(store, args.name)
        result = run_recipe(
            store, recipe_id, Fetcher(store),
            on_progress=lambda pr: print(f"  {pr.message}", flush=True),
            max_pages=args.max_pages, max_records=args.max_records,
        )
        print(f"{STATUS_TEXT[result.status]} {result.records} new records, {result.requests} requests.")
        if result.note and result.status not in ("done", "stopped"):
            print(f"  Details: {result.note}")
        _export(store, recipe_id)
        return 0 if result.status in ("done", "stopped") else 1
    elif args.cmd == "export":
        _export(store, _recipe_id(store, args.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
