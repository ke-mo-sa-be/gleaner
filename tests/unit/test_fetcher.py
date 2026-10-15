import unittest
from unittest import mock

import requests

from core.fetcher import (MIN_DELAY_FLOOR, RENDERED, USER_AGENT, BlockedError, Fetcher, RenderError,
                          looks_blocked)

PAGE = "<html><body>" + "<li>item</li>" * 40 + "</body></html>"


class MemoryStore:
    def __init__(self):
        self.pages = {}

    def get_page(self, url):
        return self.pages.get(url)

    def save_page(self, url, status, html):
        self.pages[url] = html


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



class RenderedPageTests(unittest.TestCase):
    """Pages opened in the browser follow the same rules as plain requests."""

    def fetcher(self, renderer):
        f = Fetcher(MemoryStore(), min_delay=0, max_delay=0, retry_wait=0, max_retries=1, renderer=renderer,
                    _min_delay_floor=0)
        f.allowed = lambda url: True
        return f

    def test_rendered_page_is_cached_apart_from_the_plain_page(self):
        calls = []
        f = self.fetcher(lambda url, wait_for: calls.append((url, wait_for)) or (200, PAGE))
        f.store.pages["https://example.com/list"] = "<html>plain page without the list</html>"
        self.assertEqual(f.get("https://example.com/list", render=True, wait_for="li"), PAGE)
        self.assertEqual(f.get("https://example.com/list", render=True), PAGE)  # second time from the cache
        self.assertEqual(calls, [("https://example.com/list", "li")])
        self.assertIn("https://example.com/list" + RENDERED, f.store.pages)
        self.assertEqual(f.requests_made, 1)

    def test_rendered_block_page_stops(self):
        f = self.fetcher(lambda url, wait_for: (429, PAGE))
        with self.assertRaises(BlockedError):
            f.get("https://example.com/list", render=True)
        f = self.fetcher(lambda url, wait_for: (200, "<html>Please complete the CAPTCHA</html>"))
        with self.assertRaises(BlockedError):
            f.get("https://example.com/list", render=True)

    def test_browser_failure_is_retried_like_a_network_error(self):
        answers = [RenderError("timeout"), (200, PAGE)]

        def renderer(url, wait_for):
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

        f = self.fetcher(renderer)
        with mock.patch("core.fetcher.time.sleep"):
            self.assertEqual(f.get("https://example.com/list", render=True), PAGE)
        self.assertTrue(issubclass(RenderError, requests.RequestException))

    def test_not_found_and_no_renderer(self):
        with self.assertRaises(requests.HTTPError):
            self.fetcher(lambda url, wait_for: (404, PAGE)).get("https://example.com/x", render=True)
        with self.assertRaises(RuntimeError):
            self.fetcher(None).get("https://example.com/x", render=True)


if __name__ == "__main__":
    unittest.main()
