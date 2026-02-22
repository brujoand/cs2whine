"""Unit test for coaching engine — no server needed."""

from coaching import CoachingEngine as _CoachingEngine


class CoachingEngine(_CoachingEngine):
    def process(self, data):
        live, log = super().process(data)
        return live + log

    def process_split(self, data):
        return super().process(data)


DEFAULT_WEAPONS = {
    "weapon_0": {
        "name": "weapon_knife",
        "type": "Knife",
        "state": "holstered",
    },
    "weapon_1": {
        "name": "weapon_usp_silencer",
        "type": "Pistol",
        "state": "active",
        "ammo_clip": 12,
        "ammo_clip_max": 12,
        "ammo_reserve": 24,
    },
}


def make_payload(
    round_num,
    round_phase,
    health=100,
    deaths=0,
    kills=0,
    equip_value=3000,
    bomb_state="",
    bomb_countdown=None,
    win_team="",
    team="CT",
    money=4000,
    defusekit=False,
    phase_ends_in=None,
    ct_score=0,
    t_score=0,
    weapons=None,
    round_wins=None,
    map_name="de_dust2",
    map_phase=None,
):
    p = {
        "map": {
            "name": map_name,
            "phase": map_phase or "live",
            "round": round_num,
            "team_ct": {"score": ct_score},
            "team_t": {"score": t_score},
        },
        "player": {
            "steamid": "76561198000000000",
            "name": "TestPlayer",
            "team": team,
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
    p["player"]["weapons"] = weapons if weapons is not None else DEFAULT_WEAPONS
    if bomb_state:
        p["bomb"] = {"state": bomb_state}
        if bomb_countdown is not None:
            p["bomb"]["countdown"] = bomb_countdown
    if round_wins:
        p["map"]["round_wins"] = round_wins
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
                f"death_time={r.death_time}, win={r.round_win}"
            )


def test_bomb_pressure():
    print("\n=== Test: Bomb pressure pattern ===")
    coach = CoachingEngine()
    all_tips = []

    for rnd in range(1, 8):
        all_tips.extend(coach.process(make_payload(rnd, "freezetime", team="CT", defusekit=True)))
        all_tips.extend(
            coach.process(
                make_payload(rnd, "live", team="CT", bomb_state="planted", defusekit=True)
            )
        )
        all_tips.extend(
            coach.process(make_payload(rnd, "over", team="CT", win_team="T", defusekit=True))
        )

    all_tips.extend(coach.process(make_payload(8, "freezetime", team="CT", defusekit=True)))

    if all_tips:
        for t in all_tips:
            print(f"  TIP: {t}")
    else:
        print("  NO TIPS")
        print(f"  Rounds: {len(coach.rounds)}")
        for r in coach.rounds:
            print(f"    Round {r.round_num}: bomb_planted={r.bomb_planted}")

    assert any("planted the bomb" in t.lower() for t in all_tips), (
        f"Expected bomb pressure tip, got: {all_tips}"
    )
    print("  PASS: bomb pressure pattern detected")


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


def test_eco_round_detection():
    print("\n=== Test: Eco round detection ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    coach.process(make_payload(1, "live", team="CT", defusekit=True))
    coach.process(make_payload(1, "over", team="CT", win_team="T", defusekit=True))
    tips = coach.process(
        make_payload(
            2,
            "freezetime",
            team="CT",
            money=2500,
            equip_value=800,
            defusekit=True,
            phase_ends_in=5.0,
        )
    )
    assert any("eco round" in t.lower() for t in tips), f"Expected eco round tip, got: {tips}"
    print("  PASS: eco round detection triggered")


def test_force_buy_guidance():
    print("\n=== Test: Force buy guidance ===")
    coach = CoachingEngine()
    for rnd in range(1, 3):
        coach.process(make_payload(rnd, "freezetime", team="CT", defusekit=True))
        coach.process(make_payload(rnd, "live", team="CT", defusekit=True))
        coach.process(make_payload(rnd, "over", team="CT", win_team="T", defusekit=True))
    tips = coach.process(
        make_payload(
            3,
            "freezetime",
            team="CT",
            money=2000,
            equip_value=2000,
            defusekit=True,
            phase_ends_in=5.0,
        )
    )
    assert any("force buy" in t.lower() for t in tips), f"Expected force buy tip, got: {tips}"
    print("  PASS: force buy guidance triggered")


def test_awp_playstyle():
    print("\n=== Test: AWP playstyle tip ===")
    coach = CoachingEngine()
    awp_weapons = {
        "weapon_0": {"name": "weapon_knife", "type": "Knife", "state": "holstered"},
        "weapon_1": {"name": "weapon_awp", "type": "SniperRifle", "state": "active"},
    }
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    tips = coach.process(make_payload(1, "live", team="CT", defusekit=True, weapons=awp_weapons))
    assert any("awp" in t.lower() for t in tips), f"Expected AWP tip, got: {tips}"
    print("  PASS: AWP playstyle tip triggered")


def test_smg_on_gun_round():
    print("\n=== Test: SMG on gun round ===")
    coach = CoachingEngine()
    smg_weapons = {
        "weapon_0": {"name": "weapon_knife", "type": "Knife", "state": "holstered"},
        "weapon_1": {"name": "weapon_mp9", "type": "Submachine Gun", "state": "active"},
    }
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    coach.process(make_payload(1, "live", team="CT", defusekit=True))
    coach.process(make_payload(1, "over", team="CT", win_team="CT", defusekit=True))
    for rnd in range(2, 5):
        coach.process(make_payload(rnd, "freezetime", team="CT", defusekit=True))
        coach.process(make_payload(rnd, "live", team="CT", defusekit=True))
        coach.process(make_payload(rnd, "over", team="CT", win_team="CT", defusekit=True))
    tips = coach.process(
        make_payload(
            5, "freezetime", team="CT", defusekit=True, equip_value=2500, weapons=smg_weapons
        )
    )
    tips.extend(
        coach.process(
            make_payload(
                5, "live", team="CT", defusekit=True, equip_value=2500, weapons=smg_weapons
            )
        )
    )
    assert any("smg" in t.lower() for t in tips), f"Expected SMG tip, got: {tips}"
    print("  PASS: SMG on gun round tip triggered")


def test_flash_warning():
    print("\n=== Test: Flash warning ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    p = make_payload(1, "live", team="CT", defusekit=True)
    p["player"]["state"]["flashed"] = 255
    tips = coach.process(p)
    assert any("flash" in t.lower() for t in tips), f"Expected flash tip, got: {tips}"
    print("  PASS: flash warning triggered")


def test_retake_wait():
    print("\n=== Test: CT retake wait ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    tips = coach.process(
        make_payload(
            1,
            "live",
            team="CT",
            defusekit=True,
            bomb_state="planted",
            bomb_countdown=30.0,
        )
    )
    assert any("solo retake" in t.lower() for t in tips), f"Expected retake tip, got: {tips}"
    print("  PASS: CT retake wait tip triggered")


def test_freezetime_tips_are_live():
    print("\n=== Test: Freezetime tips go to live_tips (overlay) ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    coach.process(make_payload(1, "live", team="CT", defusekit=True))
    coach.process(make_payload(1, "over", team="CT", win_team="CT", defusekit=True))
    p = make_payload(2, "freezetime", team="CT", defusekit=True, money=4000, phase_ends_in=5.0)
    p["player"]["state"]["armor"] = 0
    live, log = coach.process_split(p)
    assert any("armor" in t.lower() for t in live), (
        f"Expected armor tip in live_tips, got live={live}"
    )
    assert not any("armor" in t.lower() for t in log), f"Armor tip should not be in log_tips: {log}"
    print("  PASS: freezetime tips go to live_tips")


def test_pattern_cooldown():
    print("\n=== Test: Pattern cooldown prevents spam ===")
    coach = CoachingEngine()
    all_tips = []
    for rnd in range(1, 8):
        all_tips.extend(coach.process(make_payload(rnd, "freezetime", defusekit=True)))
        coach.process(make_payload(rnd, "live", defusekit=True))
        coach.process(
            make_payload(rnd, "live", health=0, deaths=rnd, defusekit=True, phase_ends_in=100.0)
        )
        coach.process(make_payload(rnd, "over", health=0, deaths=rnd, win_team="T", defusekit=True))
    all_tips.extend(coach.process(make_payload(8, "freezetime", defusekit=True)))
    loss_streak_tips = [t for t in all_tips if "loss streak" in t.lower()]
    assert len(loss_streak_tips) <= 2, (
        f"Expected at most 2 loss streak tips (cooldown), got "
        f"{len(loss_streak_tips)}: {loss_streak_tips}"
    )
    assert len(loss_streak_tips) >= 1, "Expected at least 1 loss streak tip"
    print(f"  PASS: {len(loss_streak_tips)} loss streak tips (cooldown working)")


def test_new_match_resets_on_map_change():
    print("\n=== Test: New match reset on map change ===")
    coach = CoachingEngine()
    for rnd in range(1, 4):
        coach.process(make_payload(rnd, "freezetime"))
        coach.process(make_payload(rnd, "live"))
        coach.process(make_payload(rnd, "over", win_team="CT"))
    assert len(coach.rounds) == 2
    # new map
    coach.process(make_payload(1, "freezetime", map_name="de_mirage"))
    assert len(coach.rounds) == 0, f"Expected reset, got {len(coach.rounds)} rounds"
    assert coach.match_map == "de_mirage"
    print("  PASS: stats reset on map change")


def test_new_match_resets_on_warmup():
    print("\n=== Test: New match reset on warmup ===")
    coach = CoachingEngine()
    for rnd in range(1, 4):
        coach.process(make_payload(rnd, "freezetime"))
        coach.process(make_payload(rnd, "live"))
        coach.process(make_payload(rnd, "over", win_team="CT"))
    assert len(coach.rounds) == 2
    # warmup phase
    coach.process(make_payload(0, "freezetime", map_phase="warmup"))
    assert len(coach.rounds) == 0, f"Expected reset, got {len(coach.rounds)} rounds"
    print("  PASS: stats reset on warmup")


def test_new_match_resets_on_round_number_drop():
    print("\n=== Test: New match reset on round number drop ===")
    coach = CoachingEngine()
    for rnd in range(1, 6):
        coach.process(make_payload(rnd, "freezetime"))
        coach.process(make_payload(rnd, "live"))
        coach.process(make_payload(rnd, "over", win_team="CT"))
    assert coach.current_round.round_num == 5
    # round drops back to 1
    coach.process(make_payload(1, "freezetime"))
    assert len(coach.rounds) == 0, f"Expected reset, got {len(coach.rounds)} rounds"
    print("  PASS: stats reset on round number drop")


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


def test_spectated_teammate_stats_ignored():
    print("\n=== Test: Spectated teammate stats ignored after death ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    coach.process(make_payload(1, "live", team="CT", health=100, kills=0, defusekit=True))
    # player dies
    coach.process(
        make_payload(
            1,
            "live",
            team="CT",
            health=0,
            deaths=1,
            kills=0,
            defusekit=True,
            phase_ends_in=90.0,
        )
    )
    assert not coach.current_round.survived, "Player should be dead"
    assert coach.current_round.kills == 0, "Player had 0 kills"
    # now spectating teammate who has 3 kills and full health
    coach.process(
        make_payload(
            1,
            "live",
            team="CT",
            health=100,
            kills=3,
            defusekit=True,
        )
    )
    assert coach.current_round.kills == 0, (
        f"Should not pick up spectated kills, got {coach.current_round.kills}"
    )
    assert not coach.current_round.survived, "Should still be dead"
    print("  PASS: spectated teammate stats ignored")


def test_no_primary_on_buy_round():
    print("\n=== Test: No primary weapon on buy round ===")
    coach = CoachingEngine()
    weapons_no_rifle = {
        "weapon_0": {"name": "weapon_knife", "type": "Knife", "state": "holstered"},
        "weapon_1": {
            "name": "weapon_usp_silencer",
            "type": "Pistol",
            "state": "active",
            "ammo_clip": 12,
        },
    }
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    coach.process(make_payload(1, "live", team="CT", defusekit=True))
    coach.process(make_payload(1, "over", team="CT", win_team="CT", defusekit=True))
    tips = coach.process(
        make_payload(
            2,
            "freezetime",
            team="CT",
            money=5000,
            equip_value=1000,
            defusekit=True,
            phase_ends_in=5.0,
            weapons=weapons_no_rifle,
        )
    )
    assert any("primary" in t.lower() for t in tips), f"Expected no-primary tip, got: {tips}"
    print("  PASS: no primary weapon warning on buy round")


def test_no_primary_tip_not_on_eco():
    print("\n=== Test: No primary tip suppressed on eco ===")
    coach = CoachingEngine()
    weapons_no_rifle = {
        "weapon_0": {"name": "weapon_knife", "type": "Knife", "state": "holstered"},
        "weapon_1": {
            "name": "weapon_usp_silencer",
            "type": "Pistol",
            "state": "active",
        },
    }
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    coach.process(make_payload(1, "live", team="CT", defusekit=True))
    coach.process(make_payload(1, "over", team="CT", win_team="T", defusekit=True))
    tips = coach.process(
        make_payload(
            2,
            "freezetime",
            team="CT",
            money=3000,
            equip_value=300,
            defusekit=True,
            phase_ends_in=5.0,
            weapons=weapons_no_rifle,
        )
    )
    assert not any("primary" in t.lower() for t in tips), f"Should not warn on eco round: {tips}"
    print("  PASS: no primary tip suppressed on eco")


def test_knife_death():
    print("\n=== Test: Knife death warning ===")
    coach = CoachingEngine()
    knife_active = {
        "weapon_0": {"name": "weapon_knife", "type": "Knife", "state": "active"},
        "weapon_1": {
            "name": "weapon_ak47",
            "type": "Rifle",
            "state": "holstered",
        },
    }
    all_tips = []
    for rnd in range(1, 4):
        all_tips.extend(coach.process(make_payload(rnd, "freezetime", team="T")))
        all_tips.extend(coach.process(make_payload(rnd, "live", team="T", weapons=knife_active)))
        all_tips.extend(
            coach.process(
                make_payload(
                    rnd,
                    "live",
                    team="T",
                    health=0,
                    deaths=rnd,
                    weapons=knife_active,
                    phase_ends_in=100.0,
                )
            )
        )
        all_tips.extend(coach.process(make_payload(rnd, "over", team="T", health=0, win_team="CT")))
    all_tips.extend(coach.process(make_payload(4, "freezetime", team="T")))
    assert any("knife" in t.lower() for t in all_tips), f"Expected knife death tip, got: {all_tips}"
    print("  PASS: knife death warning triggered")


def test_bomb_plant_loss_method():
    print("\n=== Test: Bomb plant loss method pattern ===")
    coach = CoachingEngine()
    all_tips = []
    for rnd in range(1, 5):
        all_tips.extend(coach.process(make_payload(rnd, "freezetime", team="CT", defusekit=True)))
        all_tips.extend(coach.process(make_payload(rnd, "live", team="CT", defusekit=True)))
        all_tips.extend(
            coach.process(
                make_payload(
                    rnd,
                    "over",
                    team="CT",
                    win_team="T",
                    defusekit=True,
                    round_wins={str(rnd): "t_win_bomb"},
                )
            )
        )
    all_tips.extend(coach.process(make_payload(5, "freezetime", team="CT", defusekit=True)))
    assert any("bomb plants" in t.lower() for t in all_tips), (
        f"Expected bomb plant loss tip, got: {all_tips}"
    )
    print("  PASS: bomb plant loss method pattern detected")


def test_elimination_loss_method():
    print("\n=== Test: Elimination loss method pattern ===")
    coach = CoachingEngine()
    all_tips = []
    for rnd in range(1, 5):
        all_tips.extend(coach.process(make_payload(rnd, "freezetime", team="CT", defusekit=True)))
        all_tips.extend(coach.process(make_payload(rnd, "live", team="CT", defusekit=True)))
        all_tips.extend(
            coach.process(
                make_payload(
                    rnd,
                    "over",
                    team="CT",
                    win_team="T",
                    defusekit=True,
                    round_wins={str(rnd): "t_win_elimination"},
                )
            )
        )
    all_tips.extend(coach.process(make_payload(5, "freezetime", team="CT", defusekit=True)))
    assert any("elimination" in t.lower() for t in all_tips), (
        f"Expected elimination loss tip, got: {all_tips}"
    )
    print("  PASS: elimination loss method pattern detected")


def test_no_impact_excludes_win_rounds():
    print("\n=== Test: no_impact excludes win rounds ===")

    def _die(c, rnd, win_team):
        c.process(make_payload(rnd, "freezetime", team="CT"))
        c.process(make_payload(rnd, "live", team="CT"))
        p = make_payload(rnd, "live", health=0, deaths=rnd, team="CT")
        p["phase_countdowns"] = {"phase_ends_in": 100.0}
        c.process(p)
        return c.process(make_payload(rnd, "over", health=0, win_team=win_team, team="CT"))

    coach2 = CoachingEngine()
    win_round_tips = []
    for rnd in range(1, 7):
        win_team = "T" if rnd <= 3 else "CT"
        tips = _die(coach2, rnd, win_team)
        if rnd >= 5:
            win_round_tips.extend(tips)
    assert not any("without impact" in t.lower() for t in win_round_tips), (
        f"no_impact should not fire on win rounds, got: {win_round_tips}"
    )
    print("  PASS: no_impact does not fire when dying in won rounds")


def test_damage_hit_many_finished_none():
    print("\n=== Test: Hit many opponents, finished none ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    coach.process(make_payload(1, "live", team="CT", defusekit=True))
    coach.current_round.damage_given = [
        ("A", 80, 3),
        ("B", 60, 2),
        ("C", 45, 2),
    ]
    coach.process(
        make_payload(
            1,
            "live",
            team="CT",
            health=0,
            deaths=1,
            defusekit=True,
            phase_ends_in=90.0,
        )
    )
    coach.process(make_payload(1, "over", team="CT", health=0, win_team="T", defusekit=True))
    tips = coach.process(make_payload(2, "freezetime", team="CT", defusekit=True))
    assert any("focus fire" in t.lower() for t in tips), f"Expected focus fire tip, got: {tips}"
    print("  PASS: hit many finished none tip triggered")


def test_98_damage_tip():
    print("\n=== Test: 98 damage tip ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    coach.process(make_payload(1, "live", team="CT", defusekit=True))
    coach.current_round.damage_given = [("Enemy", 98, 4)]
    coach.process(make_payload(1, "over", team="CT", win_team="T", defusekit=True))
    tips = coach.process(make_payload(2, "freezetime", team="CT", defusekit=True))
    assert any("98" in t and "headshot" in t.lower() for t in tips), (
        f"Expected 98 damage tip, got: {tips}"
    )
    print("  PASS: 98 damage tip triggered")


def test_exposed_to_many_angles():
    print("\n=== Test: Exposed to many angles ===")
    coach = CoachingEngine()
    coach.process(make_payload(1, "freezetime", team="CT", defusekit=True))
    coach.process(make_payload(1, "live", team="CT", defusekit=True))
    coach.current_round.damage_taken = [
        ("A", 25, 1),
        ("B", 30, 1),
        ("C", 20, 1),
        ("D", 25, 1),
    ]
    coach.process(
        make_payload(
            1,
            "live",
            team="CT",
            health=0,
            deaths=1,
            defusekit=True,
            phase_ends_in=90.0,
        )
    )
    coach.process(make_payload(1, "over", team="CT", health=0, win_team="T", defusekit=True))
    tips = coach.process(make_payload(2, "freezetime", team="CT", defusekit=True))
    assert any("too many angles" in t.lower() for t in tips), f"Expected angles tip, got: {tips}"
    print("  PASS: exposed to many angles tip triggered")


if __name__ == "__main__":
    test_early_deaths()
    test_bomb_pressure()
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
    test_eco_round_detection()
    test_force_buy_guidance()
    test_awp_playstyle()
    test_smg_on_gun_round()
    test_flash_warning()
    test_retake_wait()
    test_freezetime_tips_are_live()
    test_pattern_cooldown()
    test_new_match_resets_on_map_change()
    test_new_match_resets_on_warmup()
    test_new_match_resets_on_round_number_drop()
    test_context_comment_repeated_zero_kills()
    test_context_comment_repeated_trade_deaths()
    test_spectated_teammate_stats_ignored()
    test_no_primary_on_buy_round()
    test_no_primary_tip_not_on_eco()
    test_knife_death()
    test_bomb_plant_loss_method()
    test_elimination_loss_method()
    test_no_impact_excludes_win_rounds()
    test_damage_hit_many_finished_none()
    test_98_damage_tip()
    test_exposed_to_many_angles()
