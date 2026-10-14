"""Check whether a newer Gleaner installer has been published.

Two kinds of source, set in Settings (docs/ARCHITECTURE.md, "Updates"):
  github:owner/repo                 latest release of a PUBLIC GitHub repo
  \\\\server\\share\\latest.json or https://.../latest.json
                                    {"version": "0.4.0", "url": "<installer>", "notes": "..."}

Read-only: nothing is downloaded or run here. The app shows the result and lets the user decide.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import requests

from core.fetcher import USER_AGENT

GITHUB_LATEST = "https://api.github.com/repos/{repo}/releases/latest"
DEFAULT_SOURCE = "github:ke-mo-sa-be/gleaner"
TIMEOUT = 10


class UpdateError(RuntimeError):
    """The update source could not be read. Message is plain language."""


@dataclass
class UpdateInfo:
    version: str
    url: str  # installer (or release page) to open
    notes: str = ""


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
    installer = next((a.get("browser_download_url") for a in data.get("assets", [])
                      if str(a.get("name", "")).lower().endswith(".exe")), None)
    return UpdateInfo(version=str(data.get("tag_name", "")).lstrip("vV"),
                      url=installer or data.get("html_url", ""), notes=data.get("body") or "")


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
    return UpdateInfo(version=str(data["version"]), url=url, notes=str(data.get("notes", "")))


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
