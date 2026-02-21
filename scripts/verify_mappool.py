"""
Build-time check: every map in the active duty pool must have zone data in maps/zones.json.

Active duty pool last verified: 2026-02-21
Source: https://www.counter-strike.net/ / https://liquipedia.net/counterstrike/Portal:Maps/CS2
Update ACTIVE_DUTY and this comment when the pool changes.
"""

import json
import sys
from pathlib import Path

ACTIVE_DUTY = [
    "de_dust2",
    "de_mirage",
    "de_inferno",
    "de_nuke",
    "de_ancient",
    "de_overpass",
    "de_anubis",
]

zones_path = Path(__file__).parent.parent / "maps" / "zones.json"

if not zones_path.exists():
    print(f"ERROR: {zones_path} not found")
    sys.exit(1)

with zones_path.open() as f:
    zones = json.load(f)

missing = [m for m in ACTIVE_DUTY if m not in zones]
if missing:
    print(f"ERROR: missing zone data for active duty maps: {', '.join(missing)}")
    print("Add entries to maps/zones.json and update ACTIVE_DUTY in this script.")
    sys.exit(1)

print(f"OK: all {len(ACTIVE_DUTY)} active duty maps have zone data")
