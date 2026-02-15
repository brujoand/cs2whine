"""Simulate GSI payloads to test the coaching engine without CS2 running."""

import requests
import time
import json

URL = "http://127.0.0.1:3001"


def send(payload):
    r = requests.post(URL, json=payload)
    print(f"  -> {r.status_code}")
    time.sleep(0.3)


def base_payload(round_num, phase, health=100, money=4000, kills=0, deaths=0,
                 equip_value=3000, position="0, 0, 0", round_phase="live",
                 bomb_state="", bomb_position="", win_team="", flashed=0,
                 round_killhs=0, team="CT"):
    p = {
        "provider": {"name": "Counter-Strike 2", "appid": 730},
        "map": {
            "name": "de_dust2",
            "phase": "live",
            "round": round_num,
        },
        "player": {
            "steamid": "76561198000000000",
            "name": "TestPlayer",
            "team": team,
            "position": position,
            "state": {
                "health": health,
                "armor": 100,
                "money": money,
                "equip_value": equip_value,
                "round_kills": kills,
                "round_killhs": round_killhs,
                "flashed": flashed,
            },
            "match_stats": {
                "kills": kills,
                "deaths": deaths,
                "assists": 0,
                "mvps": 0,
                "score": kills * 2,
            },
        },
        "round": {
            "phase": round_phase,
        },
        "bomb": {},
    }
    if bomb_state:
        p["bomb"] = {"state": bomb_state, "position": bomb_position}
    if win_team:
        p["round"]["win_team"] = win_team
    return p


def scenario_early_deaths():
    """Player dies early 3 rounds in a row."""
    print("\n=== Scenario: Early death pattern ===")

    for rnd in range(1, 5):
        print(f"\n--- Round {rnd} freezetime ---")
        send(base_payload(rnd, "live", round_phase="freezetime"))

        print(f"--- Round {rnd} live ---")
        send(base_payload(rnd, "live", round_phase="live", health=100))

        # die quickly
        time.sleep(0.3)
        print(f"--- Round {rnd} death ---")
        send(base_payload(rnd, "live", round_phase="live", health=0,
                          deaths=rnd, position="1200, 300, 0"))

        print(f"--- Round {rnd} over (loss) ---")
        send(base_payload(rnd, "live", round_phase="over", health=0,
                          deaths=rnd, win_team="T"))


def scenario_same_spot_deaths():
    """Player keeps dying in the same location."""
    print("\n=== Scenario: Same spot deaths ===")

    for rnd in range(5, 9):
        print(f"\n--- Round {rnd} freezetime ---")
        send(base_payload(rnd, "live", round_phase="freezetime"))

        print(f"--- Round {rnd} live ---")
        send(base_payload(rnd, "live", round_phase="live"))

        # die at nearly the same position each time
        pos = f"{800 + rnd}, {200 + rnd}, 0"
        print(f"--- Round {rnd} death at {pos} ---")
        send(base_payload(rnd, "live", round_phase="live", health=0,
                          deaths=rnd, position=pos))

        send(base_payload(rnd, "live", round_phase="over", health=0,
                          deaths=rnd, win_team="T"))


def scenario_bomb_site_pattern():
    """Enemy keeps planting on the same site."""
    print("\n=== Scenario: Bomb site pattern ===")

    for rnd in range(9, 14):
        print(f"\n--- Round {rnd} freezetime ---")
        send(base_payload(rnd, "live", round_phase="freezetime"))

        print(f"--- Round {rnd} live ---")
        send(base_payload(rnd, "live", round_phase="live"))

        # bomb planted on A (positive x) every time
        send(base_payload(rnd, "live", round_phase="live",
                          bomb_state="planted", bomb_position="500, 100, 0"))

        send(base_payload(rnd, "live", round_phase="over",
                          win_team="T"))


if __name__ == "__main__":
    print("Starting GSI simulation...")
    print("Make sure gsi_server.py is running on port 3000\n")

    scenario_early_deaths()
    scenario_same_spot_deaths()
    scenario_bomb_site_pattern()

    print("\n\nDone. Check the server output for coaching tips.")
