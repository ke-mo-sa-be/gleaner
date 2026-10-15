import unittest

from core.clean import build_rows, clean_value, columns_for, extract_pincode, normalize_phones
from core.recipe import from_dict


def recipe():
    return from_dict({
        "name": "t",
        "start_url": "https://example.com/",
        "list": {"item_selector": "li", "fields": [
            {"name": "Name", "selector": "b", "required": True},
            {"name": "Phone", "selector": "i", "type": "phone", "required": True},
            {"name": "Email", "selector": "u", "type": "email"},
            {"name": "Pincode", "selector": "s", "type": "pincode"},
        ]},
        "dedup_keys": ["Name", "Phone"],
    })


def rec(key, **data):
    return {"item_key": key, "collected_at": "2026-10-14T10:00:00", "data": data}


class CleanValueTests(unittest.TestCase):
    def test_phones(self):
        self.assertEqual(normalize_phones("080-2345 6789, 98450 00000"), (["+918023456789", "+919845000000"], []))
        self.assertEqual(normalize_phones("+91 98450-00000"), (["+919845000000"], []))
        self.assertEqual(normalize_phones("12345678"), ([], ["12345678"]))
        self.assertEqual(clean_value("not a phone 12", "phone")[0], None)

    def test_phone_country(self):
        self.assertEqual(normalize_phones("0818 707 3185", "234"), (["+2348187073185"], []))
        self.assertEqual(normalize_phones("+2347000000001, +2349000000002", "91"),
                         (["+2347000000001", "+2349000000002"], []))
        self.assertEqual(normalize_phones("0044 20 7946 0000", "91"), (["+442079460000"], []))
        self.assertEqual(normalize_phones("919845000000", "91"), (["+919845000000"], []))
        self.assertEqual(normalize_phones("1234 5678", "91"), ([], ["1234 5678"]))

    def test_links_and_images_from_text(self):
        self.assertEqual(clean_value("Phone: 1 http://www.alpha.test/ more", "link"), ("http://www.alpha.test/", None))
        self.assertEqual(clean_value("https://x.test/logo.png", "image"), ("https://x.test/logo.png", None))
        self.assertEqual(clean_value("visit www.beta.test.", "link"), ("www.beta.test", None))

    def test_pincode_email_number(self):
        self.assertEqual(extract_pincode("1 MAIN RD, BANGALORE 560 001 ALL DAYS"), "560001")
        self.assertEqual(clean_value("Mail: A@B.IN / a@b.in", "email"), ("a@b.in", None))
        self.assertEqual(clean_value("since 2007", "number"), ("2007", None))
        self.assertEqual(clean_value("  spaced   text ", "text"), ("spaced text", None))
        self.assertEqual(clean_value(None, "phone"), (None, None))


class BuildRowsTests(unittest.TestCase):
    def test_split_and_issues(self):
        records = [
            rec("https://e.com/1", Name="A", Phone="9845000000", Email="bad", Pincode="BLR 560001"),
            rec("https://e.com/2", Name="A", Phone="+91 98450 00000"),           # duplicate of 1
            rec("https://e.com/list#item3", Name="B", Phone=None),               # missing required
            rec("https://e.com/4", Name="C", Phone="12"),                        # invalid required
            rec("https://e.com/5", Name="D", Phone="9845000001"),
        ]
        ready, review = build_rows(recipe(), records)
        self.assertEqual([r["Record ID"] for r in ready], ["R-00001", "R-00005"])
        self.assertEqual(ready[0]["Pincode"], "560001")
        self.assertIn("Email: invalid email", ready[0]["Issues"])
        self.assertIsNone(ready[1]["Issues"])
        self.assertEqual(ready[0]["Collected On"], "2026-10-14")
        issues = {r["Record ID"]: r["Issues"] for r in review}
        self.assertIn("duplicate of R-00001", issues["R-00002"])
        self.assertIn("Phone: missing", issues["R-00003"])
        self.assertIn("Phone: invalid phone", issues["R-00004"])
        self.assertEqual(review[1]["Source URL"], "https://e.com/list")

    def test_columns(self):
        self.assertEqual(columns_for(recipe()),
                         ["Record ID", "Name", "Phone", "Email", "Pincode", "Source URL", "Start Page", "Collected On",
                          "Issues"])


if __name__ == "__main__":
    unittest.main()
