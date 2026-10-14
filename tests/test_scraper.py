"""Offline tests on synthetic HTML shaped like drdata.in pages (no real personal data)."""

import unittest

from core.fetcher import looks_blocked
from scraper.sites import drdata
from scraper.validate import build_rows, extract_pincode, normalize_phones, normalize_role

LISTING_HTML = """
<section id="no-more-tables"><table><tbody>
<tr>
  <td data-title="Name"> DR. TEST ONE</td><td data-title="Special.">RADIOLOGIST</td>
  <td data-title="Degree">MBBS, MD</td><td data-title="State">KARNATAKA </td><td data-title="City">BANGALORE </td>
  <td data-title="Details"><a href="drtestone-radiologist-bangalore"><button>Connect Profile</button></a></td>
</tr>
<tr>
  <td data-title="Name">DR. TEST TWO</td><td data-title="Special.">CARDIOLOGIST</td>
  <td data-title="Degree">--</td><td data-title="State">KERALA</td><td data-title="City">KOCHI</td>
  <td data-title="Details"><a href="drtesttwo-cardiologist-kochi">x</a></td>
</tr>
<input type="hidden" name="pri_con_id">
</tbody></table></section>
<select id="specialization"><option value="">Select</option><option value="Radiologist">Radiologist</option></select>
"""

PROFILE_HTML = """
<div id="profile"><table><tbody>
<tr><td data-title="Name"><strong>Name</strong></td><td>DR. TEST ONE</td></tr>
<tr><td><strong>Specialization</strong></td><td>RADIOLOGIST</td></tr>
<tr><td><strong>Name of Medical Council</strong></td><td>KARNATAKA MEDICAL COUNCIL</td></tr>
<tr><td><strong>Registration Number</strong></td><td>KMC-0001</td></tr>
<tr><td><strong>Clinic/  Hospital Name</strong></td><td>TEST SCANS</td></tr>
<tr><td><strong>Date of Birth</strong></td><td>1970-01-01</td></tr>
<tr><td><strong>Address</strong></td><td>1 MAIN RD, BANGALORE 560 001 ALL DAYS</td></tr>
<tr><td><strong>Phone Number</strong></td><td>080-2345 6789, 98450 00000</td></tr>
<tr><td><strong>Member of</strong></td></tr>
</tbody></table></div>
"""


class ParseTests(unittest.TestCase):
    def test_listing(self):
        rows = drdata.parse_listing(LISTING_HTML)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "DR. TEST ONE")
        self.assertEqual(rows[0]["state"], "KARNATAKA")
        self.assertEqual(rows[0]["profile_url"], "https://www.drdata.in/drtestone-radiologist-bangalore")
        self.assertIsNone(rows[1]["degree"])

    def test_specializations(self):
        self.assertEqual(drdata.parse_specializations(LISTING_HTML), ["Radiologist"])

    def test_profile_skips_dob(self):
        p = drdata.parse_profile(PROFILE_HTML)
        self.assertEqual(p["registration_number"], "KMC-0001")
        self.assertEqual(p["facility_name"], "TEST SCANS")
        self.assertNotIn("1970-01-01", p.values())

    def test_listing_url(self):
        self.assertEqual(
            drdata.listing_url("Physician (MD Medicine)", 3),
            "https://www.drdata.in/list-doctors.php?search=Doctor&specialization=Physician%20%28MD%20Medicine%29&page=3",
        )


class ValidateTests(unittest.TestCase):
    def test_phones(self):
        self.assertEqual(normalize_phones("080-2345 6789, 98450 00000"), (["+918023456789", "+919845000000"], []))
        self.assertEqual(normalize_phones("+91 98450-00000"), (["+919845000000"], []))
        self.assertEqual(normalize_phones("12345678"), ([], ["12345678"]))
        self.assertEqual(normalize_phones(None), ([], []))

    def test_pincode(self):
        self.assertEqual(extract_pincode("1 MAIN RD, BANGALORE 560 001 ALL DAYS"), "560001")
        self.assertIsNone(extract_pincode("NO PIN HERE"))

    def test_role(self):
        self.assertEqual(normalize_role("RADIOLOGIST"), "Radiologist")
        self.assertEqual(normalize_role("Sr. Biomedical Engineer"), "BME")
        self.assertEqual(normalize_role("Purchase Manager"), "Purchase")
        self.assertEqual(normalize_role("CARDIOLOGIST"), "Doctor")

    def test_build_rows_dedup_and_review(self):
        profile = drdata.parse_profile(PROFILE_HTML)
        rec = {"source": "drdata.in", "source_url": "u1", "collected_at": "2026-10-10T10:00:00", "profile": profile}
        dup = {**rec, "source_url": "u2"}
        no_phone = {"source": "drdata.in", "source_url": "u3", "name": "DR. X", "profile": {"name": "DR. X"}}
        contacts, review = build_rows([rec, dup, no_phone])
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["Pincode"], "560001")
        self.assertEqual(contacts[0]["Role"], "Radiologist")
        self.assertEqual(contacts[0]["Collected On"], "2026-10-10")
        self.assertEqual([r["Source URL"] for r in review], ["u2", "u3"])
        self.assertIn("duplicate of DRD-00001", review[0]["Issues"])


class BlockDetectionTests(unittest.TestCase):
    def test_block_signals(self):
        self.assertTrue(looks_blocked(403, ""))
        self.assertTrue(looks_blocked(429, ""))
        self.assertTrue(looks_blocked(200, "error code: 1006"))
        self.assertTrue(looks_blocked(200, "<html>Please complete the CAPTCHA</html>"))

    def test_normal_page_with_recaptcha_widget_not_blocked(self):
        self.assertFalse(looks_blocked(200, "x" * 30_000 + "recaptcha"))


if __name__ == "__main__":
    unittest.main()
