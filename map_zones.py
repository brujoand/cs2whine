import json
import sys
from pathlib import Path


def _zones_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / "maps" / "zones.json"


def load_zones() -> dict[str, list[dict]]:
    p = _zones_path()
    if not p.exists():
        return {}
    with p.open() as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def get_zone(
    zones: dict[str, list[dict]],
    map_name: str,
    pos: tuple[float, float, float],
) -> str | None:
    map_zones = zones.get(map_name)
    if not map_zones:
        return None
    x, y, z = pos
    for zone in map_zones:
        mn, mx = zone["min"], zone["max"]
        if mn[0] <= x <= mx[0] and mn[1] <= y <= mx[1] and mn[2] <= z <= mx[2]:
            return zone["name"]
    return None
