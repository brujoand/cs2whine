import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

__version__ = "0.1.0"

GITHUB_API_URL = "https://api.github.com/repos/brujoand/cs2whine/releases/latest"
ASSET_NAME = "cs2coach.exe"


def _is_frozen():
    return getattr(sys, "frozen", False)


def _current_exe():
    return Path(sys.executable)


def _parse_version(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def _cleanup_old():
    if not _is_frozen():
        return
    old = _current_exe().with_suffix(".exe.old")
    if old.exists():
        try:
            old.unlink()
        except OSError:
            pass


def _fetch_latest_release() -> dict | None:
    req = urllib.request.Request(GITHUB_API_URL, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _find_asset_url(release: dict) -> str | None:
    for asset in release.get("assets", []):
        if asset["name"] == ASSET_NAME:
            return asset["browser_download_url"]
    return None


def _download(url: str, dest: Path):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(dest, "wb") as f:
            while chunk := resp.read(65536):
                f.write(chunk)


def _replace_and_restart(new_exe: Path):
    current = _current_exe()
    old = current.with_suffix(".exe.old")

    if old.exists():
        old.unlink()

    current.rename(old)
    new_exe.rename(current)

    subprocess.Popen([str(current)] + sys.argv[1:])
    sys.exit(0)


def check_for_update():
    _cleanup_old()

    if not _is_frozen():
        return

    try:
        release = _fetch_latest_release()
        if not release:
            return

        tag = release.get("tag_name", "")
        remote_version = _parse_version(tag)
        local_version = _parse_version(__version__)

        if remote_version <= local_version:
            return

        asset_url = _find_asset_url(release)
        if not asset_url:
            return

        print(f"Updating from {__version__} to {tag}...", flush=True)

        tmp_dir = Path(tempfile.mkdtemp())
        tmp_exe = tmp_dir / ASSET_NAME
        _download(asset_url, tmp_exe)

        _replace_and_restart(tmp_exe)

    except Exception:
        pass
