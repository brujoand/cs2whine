"""Unit test for coaching engine — no server needed."""

from coaching import CoachingEngine


def make_payload(
    round_num,
    round_phase,
    health=100,
    deaths=0,
    kills=0,
    position="0, 0, 0",
    equip_value=3000,
    bomb_state="",
    bomb_position="",
    bomb_countdown=None,
    win_team="",
    team="CT",
    money=4000,
    defusekit=False,
    phase_ends_in=None,
):
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
                "money": money,
                "equip_value": equip_value,
                "round_kills": kills,
                "round_killhs": 0,
                "flashed": 0,
                "defusekit": defusekit,
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
        if bomb_countdown is not None:
            p["bomb"]["countdown"] = bomb_countdown
    if win_team:
        p["round"]["win_team"] = win_team
    if phase_ends_in is not None:
        p["phase_countdowns"] = {"phase_ends_in": phase_ends_in}
    return p


def test_early_deaths():
    print("=== Test: Early death detection ===")
    coach = CoachingEngine()
    all_tips = []

    for rnd in range(1, 6):
        tips = coach.process(make_payload(rnd, "freezetime", defusekit=True))
        all_tips.extend(tips)

        tips = coach.process(make_payload(rnd, "live", health=100, defusekit=True))
        all_tips.extend(tips)

        tips = coach.process(
            make_payload(
                rnd,
                "live",
                health=0,
                deaths=rnd,
                position="1200, 300, 0",
                defusekit=True,
                phase_ends_in=100.0,
            )
        )
        all_tips.extend(tips)

        tips = coach.process(
            make_payload(rnd, "over", health=0, deaths=rnd, win_team="T", defusekit=True)
        )
        all_tips.extend(tips)

    if all_tips:
        for t in all_tips:
            print(f"  TIP: {t}")
    else:
        print("  NO TIPS GENERATED — investigating...")
        print(f"  Rounds recorded: {len(coach.rounds)}")
        for r in coach.rounds:
            print(
                f"    Round {r.round_num}: survived={r.survived}, "
                f"death_time={r.death_time}, death_pos={r.death_position}, "
                f"win={r.round_win}"
            )


def test_same_spot():
    print("\n=== Test: Same spot deaths ===")
    coach = CoachingEngine()
    all_tips = []

    for rnd in range(1, 7):
        tips = coach.process(make_payload(rnd, "freezetime", defusekit=True))
        all_tips.extend(tips)
        tips = coach.process(make_payload(rnd, "live", defusekit=True))
        all_tips.extend(tips)
        tips = coach.process(
            make_payload(
                rnd,
                "live",
                health=0,
                deaths=rnd,
                position="800, 200, 0",
                defusekit=True,
                phase_ends_in=100.0,
            )
        )
        all_tips.extend(tips)
        tips = coach.process(
            make_payload(rnd, "over", health=0, deaths=rnd, win_team="T", defusekit=True)
        )
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
        tips = coach.process(make_payload(rnd, "freezetime", defusekit=True))
        all_tips.extend(tips)
        tips = coach.process(
            make_payload(
                rnd,
                "live",
                bomb_state="planted",
                bomb_position="500, 100, 0",
                defusekit=True,
            )
        )
        all_tips.extend(tips)
        tips = coach.process(make_payload(rnd, "over", win_team="T", defusekit=True))
        all_tips.extend(tips)

    if all_tips:
        for t in all_tips:
            print(f"  TIP: {t}")
    else:
        print("  NO TIPS")
        print(f"  Rounds: {len(coach.rounds)}")
        for r in coach.rounds:
            print(f"    Round {r.round_num}: bomb_site={r.bomb_planted_site}")


def test_defuse_too_late_no_kit():
    print("\n=== Test: Too late to defuse (no kit) ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    tips = coach.process(
        make_payload(
            1,
            "live",
            team="CT",
            defusekit=False,
            bomb_state="planted",
            bomb_countdown=8.0,
        )
    )
    assert any("Too late to defuse" in t for t in tips), f"Expected defuse tip, got: {tips}"
    print("  PASS: tip triggered at 8s without kit (need 10s)")


def test_defuse_still_possible_with_kit():
    print("\n=== Test: Defuse still possible (with kit) ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    tips = coach.process(
        make_payload(
            1,
            "live",
            team="CT",
            defusekit=True,
            bomb_state="planted",
            bomb_countdown=8.0,
        )
    )
    assert not any("Too late to defuse" in t for t in tips), (
        f"Should not tip at 8s with kit: {tips}"
    )
    print("  PASS: no tip at 8s with kit (need 5s)")


def test_defuse_too_late_with_kit():
    print("\n=== Test: Too late to defuse (with kit) ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    tips = coach.process(
        make_payload(
            1,
            "live",
            team="CT",
            defusekit=True,
            bomb_state="planted",
            bomb_countdown=3.0,
        )
    )
    assert any("Too late to defuse" in t for t in tips), f"Expected defuse tip, got: {tips}"
    print("  PASS: tip triggered at 3s with kit (need 5s)")


def test_kit_reminder():
    print("\n=== Test: Kit reminder ===")
    coach = CoachingEngine()
    tips = coach.process(make_payload(1, "freezetime", team="CT", defusekit=False, money=4000))
    assert any("kit" in t.lower() for t in tips), f"Expected kit reminder, got: {tips}"
    print("  PASS: kit reminder triggered")


def test_kit_reminder_not_when_has_kit():
    print("\n=== Test: No kit reminder when already has kit ===")
    coach = CoachingEngine()
    tips = coach.process(make_payload(1, "freezetime", team="CT", defusekit=True, money=4000))
    assert not any("kit" in t.lower() for t in tips), f"Should not remind: {tips}"
    print("  PASS: no reminder when kit owned")


def test_kit_reminder_not_when_broke():
    print("\n=== Test: No kit reminder when can't afford ===")
    coach = CoachingEngine()
    tips = coach.process(make_payload(1, "freezetime", team="CT", defusekit=False, money=200))
    assert not any("kit" in t.lower() for t in tips), f"Should not remind: {tips}"
    print("  PASS: no reminder when broke")


def test_time_pressure():
    print("\n=== Test: Time pressure (T side) ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="T"))
    tips = coach.process(make_payload(1, "live", team="T", phase_ends_in=10.0))
    assert any("15s" in t for t in tips), f"Expected time pressure tip, got: {tips}"
    print("  PASS: time pressure tip at 10s remaining")


def test_no_time_pressure_when_bomb_planted():
    print("\n=== Test: No time pressure when bomb planted ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="T"))
    tips = coach.process(
        make_payload(
            1,
            "live",
            team="T",
            phase_ends_in=10.0,
            bomb_state="planted",
            bomb_position="500, 100, 0",
        )
    )
    assert not any("15s" in t for t in tips), f"Should not tip when planted: {tips}"
    print("  PASS: no time pressure when bomb already planted")


def test_no_time_pressure_ct_side():
    print("\n=== Test: No time pressure on CT side ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    tips = coach.process(make_payload(1, "live", team="CT", defusekit=True, phase_ends_in=10.0))
    assert not any("15s" in t for t in tips), f"Should not tip CT side: {tips}"
    print("  PASS: no time pressure on CT side")


if __name__ == "__main__":
    test_early_deaths()
    test_same_spot()
    test_bomb_pattern()
    test_defuse_too_late_no_kit()
    test_defuse_still_possible_with_kit()
    test_defuse_too_late_with_kit()
    test_kit_reminder()
    test_kit_reminder_not_when_has_kit()
    test_kit_reminder_not_when_broke()
    test_time_pressure()
    test_no_time_pressure_when_bomb_planted()
    test_no_time_pressure_ct_side()
