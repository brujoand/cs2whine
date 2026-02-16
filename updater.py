import json
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

__version__ = "0.2.1"

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


def _find_asset(release: dict) -> tuple[str, int] | None:
    for asset in release.get("assets", []):
        if asset["name"] == ASSET_NAME:
            return asset["browser_download_url"], asset["size"]
    return None


def _download(url: str, dest: Path, expected_size: int):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(dest, "wb") as f:
            while chunk := resp.read(65536):
                f.write(chunk)

    actual_size = dest.stat().st_size
    if actual_size != expected_size:
        dest.unlink()
        raise ValueError(f"Download size mismatch: expected {expected_size}, got {actual_size}")


def _replace_and_restart(new_exe: Path):
    current = _current_exe()
    old = current.with_suffix(".exe.old")

    if old.exists():
        old.unlink()

    current.rename(old)
    new_exe.rename(current)

    try:
        proc = subprocess.Popen([str(current)] + sys.argv[1:])
        try:
            proc.wait(timeout=5)
            if proc.returncode is not None and proc.returncode != 0:
                raise RuntimeError(f"New process exited with code {proc.returncode}")
        except subprocess.TimeoutExpired:
            pass
    except Exception:
        print("New version failed to start, rolling back...", flush=True)
        current.unlink(missing_ok=True)
        old.rename(current)
        return

    sys.exit(0)


def _do_update():
    try:
        release = _fetch_latest_release()
        if not release:
            return

        tag = release.get("tag_name", "")
        remote_version = _parse_version(tag)
        local_version = _parse_version(__version__)

        if remote_version <= local_version:
            return

        asset = _find_asset(release)
        if not asset:
            return
        asset_url, expected_size = asset

        print(f"Updating to {tag} in the background...", flush=True)

        tmp_dir = Path(tempfile.mkdtemp())
        tmp_exe = tmp_dir / ASSET_NAME
        _download(asset_url, tmp_exe, expected_size)

        print("Update downloaded. Restarting...", flush=True)
        _replace_and_restart(tmp_exe)

    except Exception as e:
        print(f"Update check failed: {e}", flush=True)


def check_for_update():
    _cleanup_old()

    if not _is_frozen():
        return

    threading.Thread(target=_do_update, daemon=True).start()
