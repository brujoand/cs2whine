"""Unit test for coaching engine — no server needed."""

from coaching import CoachingEngine as _CoachingEngine


class CoachingEngine(_CoachingEngine):
    def process(self, data):
        live, log = super().process(data)
        return live + log


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
    ct_score=0,
    t_score=0,
):
    p = {
        "map": {
            "name": "de_dust2",
            "phase": "live",
            "round": round_num,
            "team_ct": {"score": ct_score},
            "team_t": {"score": t_score},
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


def test_low_health_warning():
    print("\n=== Test: Low health warning ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="T"))
    # first tick: starts the timer, no tip yet
    tips = coach.process(make_payload(1, "live", team="T", health=30))
    assert not any("hold an angle" in t for t in tips), f"Should not warn on first tick: {tips}"
    # simulate delay having passed
    coach._low_hp_since -= 3.0
    tips = coach.process(make_payload(1, "live", team="T", health=30))
    assert any("hold an angle" in t for t in tips), f"Expected low hp tip, got: {tips}"
    print("  PASS: low hp warning at 30hp after delay")


def test_no_low_health_above_threshold():
    print("\n=== Test: No low health warning above threshold ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="T"))
    tips = coach.process(make_payload(1, "live", team="T", health=50))
    assert not any("hold an angle" in t for t in tips), f"Should not warn at 50hp: {tips}"
    print("  PASS: no warning at 50hp")


def test_premature_save():
    print("\n=== Test: Premature save ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="T"))
    tips = coach.process(make_payload(1, "live", team="T", equip_value=200, phase_ends_in=70.0))
    assert any("saving" in t for t in tips), f"Expected save tip, got: {tips}"
    print("  PASS: premature save warning with 70s left")


def test_no_premature_save_late():
    print("\n=== Test: No premature save when time is low ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="T"))
    tips = coach.process(make_payload(1, "live", team="T", equip_value=200, phase_ends_in=30.0))
    assert not any("saving" in t for t in tips), f"Should not warn at 30s: {tips}"
    print("  PASS: no save warning at 30s")


def test_no_armor_anti_eco():
    print("\n=== Test: No armor on anti-eco ===")
    coach = CoachingEngine()
    # round 1: win
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    coach.process(make_payload(1, "live", team="CT", defusekit=True))
    coach.process(make_payload(1, "over", team="CT", win_team="CT", defusekit=True))
    # round 2: freezetime, no armor
    tips = coach.process(make_payload(2, "freezetime", team="CT", defusekit=True, money=4000))
    # the test payload has armor=100 by default in player_state, need to override
    # let me send a payload with armor=0
    coach2 = CoachingEngine()
    coach2.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    coach2.process(make_payload(1, "live", team="CT", defusekit=True))
    coach2.process(make_payload(1, "over", team="CT", win_team="CT", defusekit=True))
    p = make_payload(2, "freezetime", team="CT", defusekit=True, money=4000, phase_ends_in=5.0)
    p["player"]["state"]["armor"] = 0
    tips = coach2.process(p)
    assert any("armor" in t.lower() for t in tips), f"Expected armor tip, got: {tips}"
    print("  PASS: no armor warning on anti-eco")


def test_eco_discipline():
    print("\n=== Test: Eco discipline ===")
    coach = CoachingEngine()
    # lose 2 rounds
    for rnd in range(1, 3):
        coach.process(make_payload(rnd, "freezetime", team="CT", defusekit=True))
        coach.process(make_payload(rnd, "live", team="CT", defusekit=True))
        coach.process(make_payload(rnd, "over", team="CT", win_team="T", defusekit=True))
    # round 3: force buy (high equip value after losses)
    tips = coach.process(
        make_payload(
            3,
            "freezetime",
            team="CT",
            defusekit=True,
            money=4000,
            equip_value=3000,
            phase_ends_in=5.0,
        )
    )
    assert any("eco" in t.lower() for t in tips), f"Expected eco tip, got: {tips}"
    print("  PASS: eco discipline warning on force buy")


def test_untraded_deaths():
    print("\n=== Test: Untraded deaths ===")
    coach = CoachingEngine()
    all_tips = []
    for rnd in range(1, 6):
        tips = coach.process(make_payload(rnd, "freezetime", defusekit=True))
        all_tips.extend(tips)
        tips = coach.process(make_payload(rnd, "live", defusekit=True))
        all_tips.extend(tips)
        tips = coach.process(
            make_payload(rnd, "live", health=0, deaths=rnd, defusekit=True, phase_ends_in=100.0)
        )
        all_tips.extend(tips)
        tips = coach.process(
            make_payload(rnd, "over", health=0, deaths=rnd, win_team="T", defusekit=True)
        )
        all_tips.extend(tips)
    assert any("without impact" in t.lower() for t in all_tips), (
        f"Expected no-impact tip, got: {all_tips}"
    )
    print("  PASS: dying without impact warning")


def test_round_zero_ignored():
    print("\n=== Test: R0 ignored ===")
    coach = CoachingEngine()
    tips = coach.process(make_payload(0, "freezetime"))
    assert not tips, f"R0 should produce no tips, got: {tips}"
    assert coach.current_round is None, "R0 should not create a round"
    print("  PASS: R0 ignored")


def test_round_win_from_scores():
    print("\n=== Test: Round win from score delta ===")
    coach = CoachingEngine()
    # R1 freezetime
    coach.process(make_payload(1, "freezetime", team="CT", ct_score=0, t_score=0))
    coach.process(make_payload(1, "live", team="CT", ct_score=0, t_score=0))
    # skip "over" — go straight to R2 freezetime with CT score bumped
    coach.process(make_payload(2, "freezetime", team="CT", ct_score=1, t_score=0))
    assert coach.rounds[-1].round_win is True, (
        f"Expected win from score delta, got {coach.rounds[-1].round_win}"
    )
    # R2: T wins
    coach.process(make_payload(2, "live", team="CT", ct_score=1, t_score=0))
    coach.process(make_payload(3, "freezetime", team="CT", ct_score=1, t_score=1))
    assert coach.rounds[-1].round_win is False, (
        f"Expected loss from score delta, got {coach.rounds[-1].round_win}"
    )
    print("  PASS: win/loss detected from score changes")


def test_survival_rate():
    print("\n=== Test: Survival rate warning ===")
    coach = CoachingEngine()
    all_tips = []
    for rnd in range(1, 8):
        tips = coach.process(
            make_payload(rnd, "freezetime", defusekit=True, ct_score=0, t_score=rnd - 1)
        )
        all_tips.extend(tips)
        coach.process(make_payload(rnd, "live", defusekit=True))
        coach.process(
            make_payload(rnd, "live", health=0, deaths=rnd, defusekit=True, phase_ends_in=100.0)
        )
        coach.process(make_payload(rnd, "over", health=0, deaths=rnd, win_team="T", defusekit=True))
    tips = coach.process(make_payload(8, "freezetime", defusekit=True, ct_score=0, t_score=7))
    all_tips.extend(tips)
    assert any("survived" in t.lower() for t in all_tips), (
        f"Expected survival rate tip, got: {all_tips}"
    )
    print("  PASS: survival rate warning triggered")


def test_going_cold():
    print("\n=== Test: Going cold detection ===")
    coach = CoachingEngine()
    all_tips = []
    # first 5 rounds: 2 kills each (good)
    for rnd in range(1, 6):
        tips = coach.process(make_payload(rnd, "freezetime", defusekit=True))
        all_tips.extend(tips)
        coach.process(make_payload(rnd, "live", kills=2, defusekit=True))
        coach.process(make_payload(rnd, "over", kills=2, win_team="CT", defusekit=True))
    # next 5 rounds: 0 kills each (cold)
    for rnd in range(6, 11):
        tips = coach.process(make_payload(rnd, "freezetime", defusekit=True))
        all_tips.extend(tips)
        coach.process(make_payload(rnd, "live", kills=0, defusekit=True))
        coach.process(make_payload(rnd, "over", kills=0, win_team="T", defusekit=True))
    tips = coach.process(make_payload(11, "freezetime", defusekit=True))
    all_tips.extend(tips)
    assert any("going cold" in t.lower() for t in all_tips), (
        f"Expected cold streak tip, got: {all_tips}"
    )
    print("  PASS: going cold detection triggered")


def test_context_comment_repeated_zero_kills():
    print("\n=== Test: Context-aware comment for repeated 0-kill rounds ===")
    from coaching import RoundSnapshot

    coach = CoachingEngine()
    for rnd in range(1, 6):
        coach.rounds.append(RoundSnapshot(round_num=rnd, kills=0, survived=False, round_win=False))
    r = RoundSnapshot(round_num=6, kills=0, survived=False, round_win=False)
    comment = coach._round_comment(r)
    assert "change positions" in comment.lower(), f"Expected context comment, got: {comment}"
    print("  PASS: repeated 0-kill comment is context-aware")


def test_context_comment_repeated_trade_deaths():
    print("\n=== Test: Context-aware comment for repeated trade deaths ===")
    from coaching import RoundSnapshot

    coach = CoachingEngine()
    for rnd in range(1, 6):
        coach.rounds.append(RoundSnapshot(round_num=rnd, kills=1, survived=False, round_win=False))
    r = RoundSnapshot(round_num=6, kills=1, survived=False, round_win=False)
    comment = coach._round_comment(r)
    assert "second in" in comment.lower(), f"Expected trade death comment, got: {comment}"
    print("  PASS: repeated trade death comment is context-aware")


if __name__ == "__main__":
    test_early_deaths()
    test_same_spot()
    test_bomb_pattern()
    test_defuse_too_late_no_kit()
    test_defuse_still_possible_with_kit()
    test_defuse_too_late_with_kit()

    test_time_pressure()
    test_no_time_pressure_when_bomb_planted()
    test_no_time_pressure_ct_side()
    test_low_health_warning()
    test_no_low_health_above_threshold()
    test_premature_save()
    test_no_premature_save_late()
    test_no_armor_anti_eco()
    test_eco_discipline()
    test_untraded_deaths()
    test_round_zero_ignored()
    test_round_win_from_scores()
    test_survival_rate()
    test_going_cold()
    test_context_comment_repeated_zero_kills()
    test_context_comment_repeated_trade_deaths()
