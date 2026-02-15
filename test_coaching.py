"""Unit test for coaching engine — no server needed."""

from coaching import CoachingEngine
import time


def make_payload(round_num, round_phase, health=100, deaths=0, kills=0,
                 position="0, 0, 0", equip_value=3000, bomb_state="",
                 bomb_position="", win_team="", team="CT"):
    p = {
        "map": {"name": "de_dust2", "phase": "live", "round": round_num},
        "player": {
            "steamid": "76561198000000000",
            "name": "TestPlayer",
            "team": team,
            "position": position,
            "state": {
                "health": health,
                "armor": 100,
                "money": 4000,
                "equip_value": equip_value,
                "round_kills": kills,
                "round_killhs": 0,
                "flashed": 0,
            },
            "match_stats": {
                "kills": kills,
                "deaths": deaths,
                "assists": 0,
                "mvps": 0,
                "score": 0,
            },
        },
        "round": {"phase": round_phase},
        "bomb": {},
    }
    if bomb_state:
        p["bomb"] = {"state": bomb_state, "position": bomb_position}
    if win_team:
        p["round"]["win_team"] = win_team
    return p


def test_early_deaths():
    print("=== Test: Early death detection ===")
    coach = CoachingEngine()
    all_tips = []

    for rnd in range(1, 6):
        tips = coach.process(make_payload(rnd, "freezetime"))
        all_tips.extend(tips)

        tips = coach.process(make_payload(rnd, "live", health=100))
        all_tips.extend(tips)

        tips = coach.process(make_payload(rnd, "live", health=0, deaths=rnd,
                                          position="1200, 300, 0"))
        all_tips.extend(tips)

        tips = coach.process(make_payload(rnd, "over", health=0, deaths=rnd,
                                          win_team="T"))
        all_tips.extend(tips)

    if all_tips:
        for t in all_tips:
            print(f"  TIP: {t}")
    else:
        print("  NO TIPS GENERATED — investigating...")
        print(f"  Rounds recorded: {len(coach.rounds)}")
        for r in coach.rounds:
            print(f"    Round {r.round_num}: survived={r.survived}, "
                  f"death_time={r.death_time}, death_pos={r.death_position}, "
                  f"win={r.round_win}")


def test_same_spot():
    print("\n=== Test: Same spot deaths ===")
    coach = CoachingEngine()
    all_tips = []

    for rnd in range(1, 7):
        tips = coach.process(make_payload(rnd, "freezetime"))
        all_tips.extend(tips)
        tips = coach.process(make_payload(rnd, "live"))
        all_tips.extend(tips)
        tips = coach.process(make_payload(rnd, "live", health=0, deaths=rnd,
                                          position=f"800, 200, 0"))
        all_tips.extend(tips)
        tips = coach.process(make_payload(rnd, "over", health=0, deaths=rnd,
                                          win_team="T"))
        all_tips.extend(tips)

    if all_tips:
        for t in all_tips:
            print(f"  TIP: {t}")
    else:
        print("  NO TIPS")


def test_bomb_pattern():
    print("\n=== Test: Bomb site pattern ===")
    coach = CoachingEngine()
    all_tips = []

    for rnd in range(1, 8):
        tips = coach.process(make_payload(rnd, "freezetime"))
        all_tips.extend(tips)
        tips = coach.process(make_payload(rnd, "live",
                                          bomb_state="planted",
                                          bomb_position="500, 100, 0"))
        all_tips.extend(tips)
        tips = coach.process(make_payload(rnd, "over", win_team="T"))
        all_tips.extend(tips)

    if all_tips:
        for t in all_tips:
            print(f"  TIP: {t}")
    else:
        print("  NO TIPS")
        print(f"  Rounds: {len(coach.rounds)}")
        for r in coach.rounds:
            print(f"    Round {r.round_num}: bomb_site={r.bomb_planted_site}")


if __name__ == "__main__":
    test_early_deaths()
    test_same_spot()
    test_bomb_pattern()
