"""Find & delete person matching, do-not-collect hashes and the schema upgrade."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from core import privacy
from core.recipe import from_dict
from core.store import SCHEMA, Store

RECIPE = from_dict({
    "name": "t", "start_url": "https://example.com/list",
    "list": {"item_selector": "li", "fields": [{"name": "Name", "selector": "b"},
                                               {"name": "Phone", "selector": "i", "type": "phone"},
                                               {"name": "Note", "selector": "u"}]},
})
DATA = {"Name": "Dr. Asha Rao", "Phone": "+91 98450 00001, 080-2345 6789", "Note": "Since 2015-06-01",
        "Email": "Asha.Rao@Example.com", "_start_page": "https://example.com/list"}


class MatchTests(unittest.TestCase):
    def test_phone_any_format(self):
        for query in ("9845000001", "098450 00001", "+919845000001", "0091 98450-00001", "080 23456789"):
            self.assertTrue(privacy.matches(DATA, query), query)
        self.assertFalse(privacy.matches(DATA, "98450 00009"))

    def test_email_and_name(self):
        self.assertTrue(privacy.matches(DATA, "asha.rao@example.com"))
        self.assertFalse(privacy.matches(DATA, "rao@other.com"))
        self.assertTrue(privacy.matches(DATA, "asha rao"))
        self.assertTrue(privacy.matches(DATA, "DR. ASHA"))
        self.assertFalse(privacy.matches(DATA, "as"))  # too short to search
        self.assertFalse(privacy.matches(DATA, "example.com/list"))  # internal columns are not searched

    def test_keys_are_hashes_of_phone_email_and_item(self):
        keys = privacy.keys_for(1, RECIPE, "https://example.com/doc/7", DATA)
        self.assertEqual(sorted(k for k, _h in keys), ["email", "item", "phone", "phone"])
        self.assertTrue(all(len(h) == 64 for _k, h in keys))
        # the date in a text column is not taken for a phone number
        other = privacy.keys_for(1, RECIPE, "https://example.com/doc/7", {**DATA, "Phone": None})
        self.assertNotIn("phone", [k for k, _h in other])
        # the same phone written differently gives the same key
        same = privacy.hashes_for(2, RECIPE, "x", {"Phone": "09845000001"})
        self.assertTrue(set(same) & set(privacy.hashes_for(1, RECIPE, "y", {"Phone": "+91 98450 00001"})))

    def test_position_keys_use_the_name_instead(self):
        keys = privacy.keys_for(1, RECIPE, "https://example.com/list#item3", {"Name": "Dr.  Asha Rao"})
        self.assertEqual([k for k, _h in keys], ["name"])
        self.assertEqual(keys, privacy.keys_for(1, RECIPE, "https://example.com/list?page=2#item0",
                                                {"Name": "dr. asha rao"}))


class UpgradeTests(unittest.TestCase):
    def test_version_1_database_gains_suppressions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.db"
            db = sqlite3.connect(path)
            db.executescript(SCHEMA)
            db.execute("PRAGMA user_version = 1")
            db.commit()
            db.close()
            store = Store(path)
            try:
                self.assertEqual(store.db.execute("PRAGMA user_version").fetchone()[0], 2)
                self.assertEqual(store.suppression_count(), 0)
                self.assertFalse(store.is_suppressed(["0" * 64]))
                self.assertFalse(store.is_suppressed([]))
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
