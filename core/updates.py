"""Check whether a newer Gleaner installer has been published.

Two kinds of source, set in Settings (docs/ARCHITECTURE.md, "Updates"):
  github:owner/repo                 latest release of a PUBLIC GitHub repo
  \\\\server\\share\\latest.json or https://.../latest.json
                                    {"version": "0.4.0", "url": "<installer>", "notes": "..."}

check() only reads version information. download() fetches the installer when the user clicks
Update now, and only keeps it if its SHA-256 matches the one the source publishes (GitHub's asset digest,
or "sha256" in latest.json). Running the installer is the app's job (app/updater.py).
"""

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import requests

from core.fetcher import USER_AGENT

GITHUB_LATEST = "https://api.github.com/repos/{repo}/releases/latest"
DEFAULT_SOURCE = "github:ke-mo-sa-be/gleaner"
TIMEOUT = 10
MAX_INSTALLER_BYTES = 600_000_000
CHUNK = 256 * 1024


class UpdateError(RuntimeError):
    """The update source could not be read. Message is plain language."""


@dataclass
class UpdateInfo:
    version: str
    url: str  # installer (or release page) to open
    notes: str = ""
    sha256: str = ""  # of the installer, when the source publishes it

    @property
    def can_download(self) -> bool:
        """An installer we can fetch and verify ourselves (not just a release page)."""
        return self.url.lower().endswith(".exe") and (bool(self.sha256) or not self.url.lower().startswith("http"))


def parse_version(text) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", str(text or ""))
    return tuple(int(n) for n in numbers[:3]) or (0,)


def is_newer(candidate, current) -> bool:
    return parse_version(candidate) > parse_version(current)


def _get_json(url):
    try:
        resp = requests.get(url, timeout=TIMEOUT,
                            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    except requests.RequestException as exc:
        raise UpdateError("Couldn't reach the update source. Check the internet connection.") from exc
    if resp.status_code == 404:
        raise UpdateError("The update source has no published versions yet (or is not public).")
    if resp.status_code != 200:
        raise UpdateError(f"The update source answered with an error ({resp.status_code}).")
    try:
        return resp.json()
    except ValueError as exc:
        raise UpdateError("The update source sent something that isn't a version file.") from exc


def _from_github(repo) -> UpdateInfo:
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise UpdateError("The GitHub source must look like github:owner/repo.")
    data = _get_json(GITHUB_LATEST.format(repo=repo))
    asset = next((a for a in data.get("assets", []) if str(a.get("name", "")).lower().endswith(".exe")), None)
    digest = str((asset or {}).get("digest") or "")
    return UpdateInfo(version=str(data.get("tag_name", "")).lstrip("vV"),
                      url=(asset or {}).get("browser_download_url") or data.get("html_url", ""),
                      notes=data.get("body") or "",
                      sha256=digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else "")


def _from_manifest(source) -> UpdateInfo:
    if source.lower().startswith("https://"):
        data = _get_json(source)
    elif source.lower().startswith("http://"):
        raise UpdateError("Use an https:// address or a shared-folder path for updates.")
    else:
        try:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise UpdateError("Couldn't read the version file in the shared folder.") from exc
    if not isinstance(data, dict) or not data.get("version") or not data.get("url"):
        raise UpdateError("The version file needs 'version' and 'url'.")
    url = str(data["url"])
    if url.lower().startswith("http://"):
        raise UpdateError("The installer address must use https://.")
    if not url.lower().startswith("https://") and not Path(url).is_absolute():
        url = str(Path(source).parent / url)  # installer next to latest.json in the shared folder
    return UpdateInfo(version=str(data["version"]), url=url, notes=str(data.get("notes", "")),
                      sha256=str(data.get("sha256", "")).lower())


def check(source: str, current: str) -> UpdateInfo | None:
    """Return UpdateInfo if the source has a newer version than `current`, else None. Raises UpdateError."""
    source = (source or "").strip()
    if not source:
        raise UpdateError("No update source is set.")
    if source.lower().startswith("github:"):
        info = _from_github(source[len("github:"):])
    else:
        info = _from_manifest(source)
    return info if is_newer(info.version, current) else None


def download(info: UpdateInfo, folder, progress=None) -> Path:
    """Fetch the installer into folder and return its path. progress(done_bytes, total_bytes or 0).

    Raises UpdateError when it can't be fetched or doesn't match the published SHA-256."""
    if not info.can_download:
        raise UpdateError("This version can't be checked automatically. Download it from the release page.")
    name = re.sub(r"[^\w.-]", "_", Path(info.url.split("?")[0]).name) or "Gleaner-Setup.exe"
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target, partial = folder / name, folder / (name + ".part")
    digest = hashlib.sha256()
    try:
        if info.url.lower().startswith("https://"):
            _fetch(info.url, partial, digest, progress)
        elif info.url.lower().startswith("http"):
            raise UpdateError("The installer address must use https://.")
        else:  # installer in a shared folder
            source = Path(info.url)
            total = source.stat().st_size
            with source.open("rb") as src, partial.open("wb") as out:
                done = 0
                while chunk := src.read(CHUNK):
                    out.write(chunk)
                    digest.update(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except OSError as exc:
        partial.unlink(missing_ok=True)
        raise UpdateError("Couldn't save or read the new installer.") from exc
    except requests.RequestException as exc:
        partial.unlink(missing_ok=True)
        raise UpdateError("The download stopped. Check the internet connection and try again.") from exc
    except UpdateError:
        partial.unlink(missing_ok=True)
        raise
    if info.sha256 and digest.hexdigest() != info.sha256:
        partial.unlink(missing_ok=True)
        raise UpdateError("The downloaded installer doesn't match the published version, so it was deleted. "
                          "Try again later.")
    partial.replace(target)
    return target


def _fetch(url, partial, digest, progress):
    with requests.get(url, stream=True, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as resp:
        if resp.status_code != 200:
            raise UpdateError(f"The download failed ({resp.status_code}).")
        total = int(resp.headers.get("Content-Length") or 0)
        if total > MAX_INSTALLER_BYTES:
            raise UpdateError("The download is far bigger than an installer should be.")
        done = 0
        with partial.open("wb") as out:
            for chunk in resp.iter_content(CHUNK):
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if done > MAX_INSTALLER_BYTES:
                    raise UpdateError("The download is far bigger than an installer should be.")
                if progress:
                    progress(done, total)
