import unittest

from core.fetcher import MIN_DELAY_FLOOR, USER_AGENT, Fetcher, looks_blocked


class BlockDetectionTests(unittest.TestCase):
    def test_status_codes(self):
        for status in (401, 403, 407, 429, 503):
            self.assertTrue(looks_blocked(status, "<html>" + "x" * 30_000))
        self.assertFalse(looks_blocked(200, "<html>" + "x" * 30_000))

    def test_cloudflare_and_captcha_pages(self):
        self.assertTrue(looks_blocked(200, "error code: 1006"))
        self.assertTrue(looks_blocked(200, "x" * 50_000 + "cf-chl-bypass"))
        self.assertTrue(looks_blocked(200, "<html>Please complete the CAPTCHA</html>"))

    def test_normal_page_with_recaptcha_widget_not_blocked(self):
        self.assertFalse(looks_blocked(200, "x" * 30_000 + "recaptcha"))


class SafetyRuleTests(unittest.TestCase):
    def test_delay_floor_cannot_be_lowered_by_settings(self):
        f = Fetcher(store=None, min_delay=0, max_delay=1)
        self.assertEqual(f.min_delay, MIN_DELAY_FLOOR)
        self.assertGreaterEqual(f.max_delay, f.min_delay)

    def test_user_agent_identifies_tool(self):
        self.assertIn("Gleaner", USER_AGENT)
        self.assertIn("Gleaner", Fetcher(store=None).session.headers["User-Agent"])


if __name__ == "__main__":
    unittest.main()
