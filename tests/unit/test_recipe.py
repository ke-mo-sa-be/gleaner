import copy
import json
import unittest
from pathlib import Path

from core.recipe import RecipeError, check_url, from_dict, load_recipe, validate

ROOT = Path(__file__).resolve().parents[2]
DRDATA = ROOT / "recipes" / "drdata.json"


def base():
    return {
        "name": "Test",
        "start_url": "https://example.com/list",
        "list": {"item_selector": "li.item", "fields": [
            {"name": "Name", "selector": "b", "type": "text", "required": True},
            {"name": "Link", "selector": "a", "attr": "href", "type": "link"},
        ]},
        "pagination": {"type": "none"},
    }


class RecipeTests(unittest.TestCase):
    def test_shipped_drdata_recipe_is_valid(self):
        validate(load_recipe(DRDATA))

    def test_round_trip(self):
        recipe = load_recipe(DRDATA)
        again = from_dict(json.loads(recipe.to_json()))
        self.assertEqual(recipe, again)

    def test_start_pages(self):
        data = base()
        data["start_urls"] = ["https://example.com/list?city=a", "https://example.com/list?city=b"]
        del data["start_url"]
        recipe = from_dict(data)
        self.assertEqual(recipe.start_url, "https://example.com/list?city=a")
        self.assertEqual(recipe.start_pages(), data["start_urls"])
        validate(recipe)
        self.assertEqual(from_dict(json.loads(recipe.to_json())), recipe)
        self.assertEqual(from_dict(base()).start_pages(), ["https://example.com/list"])

    def test_start_page_problems(self):
        data = base()
        data["start_urls"] = ["https://example.com/a", "https://example.com/a", "http://127.0.0.1/x"]
        data["start_url"] = "https://example.com/other"
        with self.assertRaises(RecipeError) as ctx:
            validate(from_dict(data))
        text = str(ctx.exception)
        self.assertIn("listed twice", text)
        self.assertIn("local network", text)
        data["start_urls"] = "https://example.com/a"
        with self.assertRaises(RecipeError):
            from_dict(data)

    def test_unknown_key_rejected(self):
        data = base()
        data["proxy"] = "http://x"
        with self.assertRaises(RecipeError) as ctx:
            from_dict(data)
        self.assertIn("unknown keys", str(ctx.exception))

    def test_unknown_field_key_rejected(self):
        data = base()
        data["list"]["fields"][0]["xpath"] = "//b"
        with self.assertRaises(RecipeError):
            from_dict(data)

    def test_local_and_non_http_urls_rejected(self):
        self.assertIsNotNone(check_url("http://127.0.0.1:8000/"))
        self.assertIsNotNone(check_url("http://192.168.1.5/"))
        self.assertIsNotNone(check_url("http://localhost/"))
        self.assertIsNotNone(check_url("file:///C:/x.html"))
        self.assertIsNotNone(check_url("javascript:alert(1)"))
        self.assertIsNone(check_url("http://127.0.0.1:8000/", allow_local=True))
        self.assertIsNone(check_url("https://www.drdata.in/list-doctors.php"))

    def test_label_only_on_detail(self):
        data = base()
        data["list"]["fields"].append({"name": "Phone", "label": "Phone", "label_scope": "tr"})
        with self.assertRaises(RecipeError) as ctx:
            validate(from_dict(data))
        self.assertIn("only allowed on detail", str(ctx.exception))

    def test_detail_link_field_must_exist(self):
        data = base()
        data["detail"] = {"link_field": "Nope", "fields": [{"name": "Phone", "label": "Phone", "label_scope": "tr"}]}
        with self.assertRaises(RecipeError) as ctx:
            validate(from_dict(data))
        self.assertIn("link_field", str(ctx.exception))

    def test_bad_selector_and_type(self):
        data = base()
        data["list"]["fields"][0]["selector"] = "b[["
        data["list"]["fields"][1]["type"] = "colour"
        with self.assertRaises(RecipeError) as ctx:
            validate(from_dict(data))
        self.assertEqual(len(ctx.exception.problems), 2)

    def test_duplicate_names_and_dedup_keys(self):
        data = base()
        data["list"]["fields"][1]["name"] = "Name"
        data["dedup_keys"] = ["Phone"]
        with self.assertRaises(RecipeError) as ctx:
            validate(from_dict(data))
        text = str(ctx.exception)
        self.assertIn("duplicate field names", text)
        self.assertIn("dedup key 'Phone'", text)

    def test_pagination_requirements(self):
        data = copy.deepcopy(base())
        data["pagination"] = {"type": "next_link"}
        with self.assertRaises(RecipeError):
            validate(from_dict(data))
        data["pagination"] = {"type": "page_param"}
        with self.assertRaises(RecipeError):
            validate(from_dict(data))


if __name__ == "__main__":
    unittest.main()
