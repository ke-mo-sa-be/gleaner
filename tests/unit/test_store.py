import tempfile
import unittest
from pathlib import Path

from core.recipe import RecipeError, load_recipe
from core.store import Store

DRDATA = Path(__file__).resolve().parents[2] / "recipes" / "drdata.json"


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.db")
        self.recipe = load_recipe(DRDATA)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_recipe_round_trip_and_update(self):
        rid = self.store.save_recipe(self.recipe)
        self.assertEqual(self.store.get_recipe(rid), self.recipe)
        self.assertEqual(self.store.find_recipe(self.recipe.name), rid)
        self.recipe.max_records = 5
        self.store.save_recipe(self.recipe, rid)
        self.assertEqual(self.store.get_recipe(rid).max_records, 5)

    def test_invalid_recipe_not_saved(self):
        self.recipe.start_url = "http://127.0.0.1/"
        with self.assertRaises(RecipeError):
            self.store.save_recipe(self.recipe)
        self.assertEqual(self.store.list_recipes(), [])

    def test_records_unique_per_key_and_cascade(self):
        rid = self.store.save_recipe(self.recipe)
        self.store.save_record(rid, "k1", {"Name": "A"})
        self.store.save_record(rid, "k1", {"Name": "A2"})
        self.store.save_record(rid, "k2", {"Name": "B"})
        self.assertTrue(self.store.has_record(rid, "k1"))
        self.assertEqual(sorted(r["data"]["Name"] for r in self.store.records(rid)), ["A2", "B"])
        run = self.store.start_run(rid)
        self.store.finish_run(run, "done", 3, 1, 2)
        self.store.delete_recipe(rid)
        self.assertEqual(self.store.records(rid), [])
        self.assertEqual(self.store.runs(rid), [])

    def test_runs_and_library_status(self):
        rid = self.store.save_recipe(self.recipe)
        r1 = self.store.start_run(rid)
        self.store.finish_run(r1, "blocked", 5, 1, 2, "HTTP 429")
        self.store.start_run(rid)  # left running, as after a crash
        self.assertEqual(self.store.mark_interrupted(), 1)
        lib = self.store.list_recipes()[0]
        self.assertEqual(lib["last_status"], "interrupted")
        self.assertEqual([r["status"] for r in self.store.runs(rid)], ["blocked", "interrupted"])


if __name__ == "__main__":
    unittest.main()
