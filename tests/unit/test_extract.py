import unittest

from core.extract import extract_detail, extract_list, next_page_url, with_query_param
from core.recipe import from_dict

LISTING = """
<table id="t"><tbody>
<tr><td data-title="Name"> DR. TEST ONE</td><td data-title="City">BANGALORE </td>
    <td><a href="/dr-one"><button>Profile</button></a></td></tr>
<tr><td data-title="Name">DR. TEST TWO</td><td data-title="City"></td>
    <td><a href="dr-two">Profile</a></td></tr>
</tbody></table>
<a class="next" href="/list?page=2">Next</a>
"""

DETAIL = """
<div id="profile"><table>
<tr><td><strong>Phone Number</strong></td><td>98450 00000</td></tr>
<tr><td><strong>Clinic/  Hospital Name :</strong></td><td>TEST SCANS</td></tr>
<tr><td><strong>Date of Birth</strong></td><td>1970-01-01</td></tr>
</table>
<dl><dt>Email</dt><dd>a@b.in</dd></dl></div>
"""


def recipe(**overrides):
    data = {
        "name": "t",
        "start_url": "https://example.com/list",
        "list": {"item_selector": "#t tbody tr", "fields": [
            {"name": "Name", "selector": "td[data-title=\"Name\"]"},
            {"name": "City", "selector": "td[data-title=\"City\"]"},
            {"name": "Profile", "selector": "td:last-child a, td:last-child button", "attr": "href", "type": "link"},
        ]},
        "detail": {"link_field": "Profile", "fields": [
            {"name": "Phone", "label": "Phone Number", "label_scope": "#profile tr", "type": "phone"},
            {"name": "Clinic", "label": "clinic/ hospital name", "label_scope": "#profile tr"},
            {"name": "Email", "label": "Email", "label_scope": "#profile dt", "type": "email"},
            {"name": "Missing", "label": "Fax", "label_scope": "#profile tr"},
        ]},
    }
    data.update(overrides)
    return from_dict(data)


class ExtractTests(unittest.TestCase):
    def test_list_fields_and_links(self):
        rows = extract_list(LISTING, recipe(), "https://example.com/list")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Name"], "DR. TEST ONE")
        self.assertEqual(rows[0]["City"], "BANGALORE")
        self.assertIsNone(rows[1]["City"])
        self.assertEqual(rows[0]["Profile"], "https://example.com/dr-one")
        self.assertEqual(rows[1]["Profile"], "https://example.com/dr-two")

    def test_button_inside_link_uses_link_href(self):
        r = recipe(list={"item_selector": "#t tbody tr", "fields": [
            {"name": "Profile", "selector": "button", "attr": "href", "type": "link"}]}, detail=None)
        rows = extract_list(LISTING, r, "https://example.com/list")
        self.assertEqual(rows[0]["Profile"], "https://example.com/dr-one")
        self.assertEqual(len(rows), 1)  # row 2 has no button: nothing matched, so it is dropped

    def test_scope_selector_means_item_itself(self):
        r = recipe(list={"item_selector": "td[data-title=\"Name\"]", "fields": [{"name": "N", "selector": ":scope"}]},
                   detail=None)
        self.assertEqual([x["N"] for x in extract_list(LISTING, r, "https://example.com/")],
                         ["DR. TEST ONE", "DR. TEST TWO"])

    def test_detail_labels(self):
        data = extract_detail(DETAIL, recipe(), "https://example.com/dr-one")
        self.assertEqual(data["Phone"], "98450 00000")
        self.assertEqual(data["Clinic"], "TEST SCANS")  # case, colon and spacing ignored
        self.assertEqual(data["Email"], "a@b.in")  # dt/dd style
        self.assertIsNone(data["Missing"])
        self.assertNotIn("1970-01-01", data.values())

    def test_page_param(self):
        r = recipe(pagination={"type": "page_param", "param": "page", "start": 1})
        self.assertEqual(next_page_url("", r, "https://example.com/list?x=1", 1), "https://example.com/list?x=1&page=2")
        self.assertEqual(with_query_param("https://e.com/l?page=2&a=b", "page", 3), "https://e.com/l?a=b&page=3")

    def test_next_link_and_max_pages(self):
        r = recipe(pagination={"type": "next_link", "selector": "a.next", "max_pages": 2})
        self.assertEqual(next_page_url(LISTING, r, "https://example.com/list", 1), "https://example.com/list?page=2")
        self.assertIsNone(next_page_url(LISTING, r, "https://example.com/list", 2))
        self.assertIsNone(next_page_url("<p>no next</p>", r, "https://example.com/list", 1))

    def test_next_link_by_text(self):
        html = '<div class="pg"><a href="?p=1">1</a><a href="?p=3">Next &raquo;</a><a href="?p=9">Last</a></div>'
        r = recipe(pagination={"type": "next_link", "selector": "div.pg a", "text": "next »"})
        self.assertEqual(next_page_url(html, r, "https://example.com/list?p=2", 1), "https://example.com/list?p=3")

    def test_no_pagination(self):
        self.assertIsNone(next_page_url(LISTING, recipe(), "https://example.com/list", 1))


if __name__ == "__main__":
    unittest.main()
