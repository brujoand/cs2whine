import json
import sys
import threading
import urllib.request

__version__ = "0.2.1"

GITHUB_API_URL = "https://api.github.com/repos/brujoand/cs2whine/releases/latest"


def _is_frozen():
    return getattr(sys, "frozen", False)


def _parse_version(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def _fetch_latest_release() -> dict | None:
    req = urllib.request.Request(GITHUB_API_URL, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _do_update_check():
    try:
        release = _fetch_latest_release()
        if not release:
            return

        tag = release.get("tag_name", "")
        remote_version = _parse_version(tag)
        local_version = _parse_version(__version__)

        if remote_version <= local_version:
            return

        html_url = release.get(
            "html_url", f"https://github.com/brujoand/cs2whine/releases/tag/{tag}"
        )
        print(f"New version available: {tag} (current: v{__version__})", flush=True)
        print(f"Download: {html_url}", flush=True)

        if sys.platform == "win32":
            from notify import _show_windows_toast

            _show_windows_toast(
                "cs2whine", f"Update available: {tag}\nVisit GitHub releases to download."
            )

    except Exception as e:
        print(f"Update check failed: {e}", flush=True)


def check_for_update():
    if not _is_frozen():
        return

    threading.Thread(target=_do_update_check, daemon=True).start()
