import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import updates
from core.updates import UpdateError, check, is_newer, parse_version


class FakeResponse:
    def __init__(self, status, data):
        self.status_code = status
        self._data = data

    def json(self):
        return self._data


class VersionTests(unittest.TestCase):
    def test_compare(self):
        self.assertEqual(parse_version("v0.10.2"), (0, 10, 2))
        self.assertTrue(is_newer("0.10.0", "0.9.9"))
        self.assertFalse(is_newer("0.4.0", "0.4.0"))
        self.assertFalse(is_newer("0.3.9", "0.4"))


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.manifest = Path(self.tmp.name) / "latest.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data):
        self.manifest.write_text(json.dumps(data), encoding="utf-8")

    def test_shared_folder_newer_version(self):
        self.write({"version": "0.5.0", "url": "Gleaner-Setup-0.5.0.exe", "notes": "Faster preview"})
        info = check(str(self.manifest), "0.4.0")
        self.assertEqual(info.version, "0.5.0")
        self.assertEqual(Path(info.url), Path(self.tmp.name) / "Gleaner-Setup-0.5.0.exe")
        self.assertEqual(info.notes, "Faster preview")

    def test_same_version_means_no_update(self):
        self.write({"version": "0.4.0", "url": "x.exe"})
        self.assertIsNone(check(str(self.manifest), "0.4.0"))

    def test_bad_sources(self):
        with self.assertRaises(UpdateError):
            check("", "0.4.0")
        with self.assertRaises(UpdateError):
            check(str(self.manifest), "0.4.0")  # missing file
        self.write({"version": "0.5.0"})
        with self.assertRaises(UpdateError):
            check(str(self.manifest), "0.4.0")  # no url
        self.write({"version": "0.5.0", "url": "http://insecure.example/x.exe"})
        with self.assertRaises(UpdateError):
            check(str(self.manifest), "0.4.0")
        with self.assertRaises(UpdateError):
            check("http://example.com/latest.json", "0.4.0")


class GitHubTests(unittest.TestCase):
    def test_latest_release_with_installer_asset(self):
        release = {"tag_name": "v0.5.0", "body": "Notes", "html_url": "https://github.com/o/r/releases/v0.5.0",
                   "assets": [{"name": "Gleaner-Setup-0.5.0.exe",
                               "browser_download_url": "https://github.com/o/r/releases/download/v0.5.0/G.exe"}]}
        with mock.patch.object(updates.requests, "get", return_value=FakeResponse(200, release)) as get:
            info = check("github:o/r", "0.4.0")
        self.assertIn("/repos/o/r/releases/latest", get.call_args.args[0])
        self.assertEqual((info.version, info.url), ("0.5.0", "https://github.com/o/r/releases/download/v0.5.0/G.exe"))

    def test_private_or_empty_repo(self):
        with mock.patch.object(updates.requests, "get", return_value=FakeResponse(404, {})):
            with self.assertRaises(UpdateError) as ctx:
                check("github:o/r", "0.4.0")
        self.assertIn("not public", str(ctx.exception))

    def test_bad_repo_name(self):
        with self.assertRaises(UpdateError):
            check("github:not a repo", "0.4.0")





class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.installer = self.folder / "share" / "Gleaner-Setup-0.9.0.exe"
        self.installer.parent.mkdir()
        self.installer.write_bytes(b"MZ" + b"x" * 300_000)
        import hashlib
        self.sha = hashlib.sha256(self.installer.read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def test_shared_folder_copy_verified(self):
        seen = []
        info = updates.UpdateInfo("0.9.0", str(self.installer), sha256=self.sha)
        path = updates.download(info, self.folder / "updates", lambda done, total: seen.append((done, total)))
        self.assertEqual(path.read_bytes(), self.installer.read_bytes())
        self.assertEqual(seen[-1], (300_002, 300_002))
        self.assertFalse(list((self.folder / "updates").glob("*.part")))

    def test_mismatch_is_deleted(self):
        info = updates.UpdateInfo("0.9.0", str(self.installer), sha256="0" * 64)
        with self.assertRaises(UpdateError):
            updates.download(info, self.folder / "updates")
        self.assertEqual(list((self.folder / "updates").iterdir()), [])

    def test_https_needs_a_published_checksum(self):
        info = updates.UpdateInfo("0.9.0", "https://example.com/Gleaner-Setup-0.9.0.exe")
        self.assertFalse(info.can_download)
        with self.assertRaises(UpdateError):
            updates.download(info, self.folder / "updates")
        page = updates.UpdateInfo("0.9.0", "https://github.com/o/r/releases/v0.9.0", sha256=self.sha)
        self.assertFalse(page.can_download)  # a release page, not an installer

    def test_https_stream_verified(self):
        body = self.installer.read_bytes()

        class Stream:
            status_code = 200
            headers = {"Content-Length": str(len(body))}

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def iter_content(self, size):
                for i in range(0, len(body), size):
                    yield body[i:i + size]

        info = updates.UpdateInfo("0.9.0", "https://example.com/Gleaner-Setup-0.9.0.exe", sha256=self.sha)
        with mock.patch.object(updates.requests, "get", return_value=Stream()):
            path = updates.download(info, self.folder / "updates")
        self.assertEqual(path.name, "Gleaner-Setup-0.9.0.exe")

    def test_github_digest_is_read(self):
        release = {"tag_name": "v0.9.0", "body": "", "html_url": "https://github.com/o/r/releases/v0.9.0",
                   "assets": [{"name": "Gleaner-Setup-0.9.0.exe", "digest": "sha256:" + "AB" * 32,
                               "browser_download_url": "https://github.com/o/r/releases/download/v0.9.0/G.exe"}]}
        with mock.patch.object(updates.requests, "get", return_value=FakeResponse(200, release)):
            info = check("github:o/r", "0.8.0")
        self.assertEqual(info.sha256, "ab" * 32)
        self.assertTrue(info.can_download)


if __name__ == "__main__":
    unittest.main()
