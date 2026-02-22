import time
from collections import Counter, deque
from dataclasses import dataclass, field

DEFUSE_TIME_KIT = 5.0
DEFUSE_TIME_NO_KIT = 10.0
TIME_PRESSURE_THRESHOLD = 15.0
LOW_HP_THRESHOLD = 35
SAVE_TIME_THRESHOLD = 60.0
SAVE_EQUIP_THRESHOLD = 500
FORCE_BUY_EQUIP_THRESHOLD = 2000
FREEZETIME_BUY_WINDOW = 15.0
LOW_HP_DELAY = 2.0
RIFLE_BUY_THRESHOLD = 2700
FULL_BUY_THRESHOLD = 4750
ECO_EQUIP_THRESHOLD = 1500
ECO_MONEY_THRESHOLD = 3000
FORCE_EQUIP_LOW = 1500
FORCE_EQUIP_HIGH = 3000
PRIMARY_TYPES = {"Rifle", "SniperRifle", "Shotgun", "Submachine Gun", "Machine Gun"}
RETAKE_BOMB_THRESHOLD = 15.0
BOMB_COUNTDOWN_THRESHOLDS = (20, 15, 10, 7, 5, 4, 3, 2, 1)


@dataclass
class RoundSnapshot:
    round_num: int
    phase: str = ""
    death_time: float | None = None
    kills: int = 0
    hs_kills: int = 0
    equipment_value: int = 0
    armor: int = 0
    team_money: int = 0
    survived: bool = True
    bomb_planted: bool = False
    round_win: bool | None = None
    has_primary: bool = False
    active_weapon_type: str = ""
    weapon_at_death: str = ""
    win_method: str = ""
    damage_given: list[tuple[str, int, int]] = field(default_factory=list)
    damage_taken: list[tuple[str, int, int]] = field(default_factory=list)


class CoachingEngine:
    def __init__(self):
        self.rounds: deque[RoundSnapshot] = deque(maxlen=30)
        self.current_round: RoundSnapshot | None = None
        self.prev_state: dict = {}
        self.match_map: str = ""
        self.my_team: str = ""
        self.round_duration: float = 115.0
        self.emitted_tips: set = set()
        self._last_pattern: dict = {}
        self._pattern_cooldown: dict[str, int] = {}
        self.pending_round_stats: str | None = None
        self.pending_round_comment: str | None = None
        self._low_hp_since: float | None = None
        self._prev_ct_score: int = 0
        self._prev_t_score: int = 0

    def _reset_match(self):
        self.rounds.clear()
        self.current_round = None
        self.prev_state.clear()
        self.my_team = ""
        self.emitted_tips.clear()
        self._last_pattern.clear()
        self._pattern_cooldown.clear()
        self.pending_round_stats = None
        self.pending_round_comment = None
        self._low_hp_since = None
        self._prev_ct_score = 0
        self._prev_t_score = 0

    def process(self, data: dict) -> tuple[list[str], list[str]]:
        live_tips: list[str] = []
        log_tips: list[str] = []

        map_data = data.get("map", {})
        player = data.get("player", {})
        player_state = player.get("state", {})
        match_stats = player.get("match_stats", {})
        round_data = data.get("round", {})
        bomb = data.get("bomb", {})
        phase_countdowns = data.get("phase_countdowns", {})

        if not player or not map_data:
            return live_tips, log_tips

        provider_steam = data.get("provider", {}).get("steamid", "")
        player_steam = player.get("steamid", "")
        if provider_steam and player_steam and provider_steam != player_steam:
            return live_tips, log_tips

        current_round_num = map_data.get("round", 0)
        round_phase = round_data.get("phase", "")
        map_phase = map_data.get("phase", "")
        map_name = map_data.get("name", "")

        # detect new match: map change, warmup after playing, or round number reset
        new_match = False
        if self.match_map and map_name and map_name != self.match_map:
            new_match = True
        elif map_phase == "warmup" and self.rounds:
            new_match = True
        elif (
            self.current_round
            and current_round_num < self.current_round.round_num
            and current_round_num <= 1
        ):
            new_match = True
        if new_match:
            self._reset_match()

        self.match_map = map_name
        new_team = player.get("team", "")
        if new_team != self.my_team:
            self._last_pattern.clear()
            self._pattern_cooldown.clear()
        self.my_team = new_team

        if map_phase == "warmup":
            return live_tips, log_tips

        if current_round_num == 0:
            return live_tips, log_tips

        ct_score = map_data.get("team_ct", {}).get("score", 0)
        t_score = map_data.get("team_t", {}).get("score", 0)

        # new round started
        if round_phase == "freezetime" and (
            self.current_round is None or self.current_round.round_num != current_round_num
        ):
            if self.current_round:
                prev_team = self.prev_state.get("team", self.my_team)
                if self.current_round.round_win is None and prev_team:
                    my_prev = self._prev_ct_score if prev_team == "CT" else self._prev_t_score
                    my_curr = ct_score if prev_team == "CT" else t_score
                    if my_curr > my_prev:
                        self.current_round.round_win = True
                    elif (ct_score + t_score) > (self._prev_ct_score + self._prev_t_score):
                        self.current_round.round_win = False
                self.rounds.append(self.current_round)
                log_tips.extend(self._analyze_on_round_end())
                self.pending_round_stats = self._format_round_stats(match_stats)
                self.pending_round_comment = self._round_comment(self.rounds[-1])
            self._prev_ct_score = ct_score
            self._prev_t_score = t_score
            self.current_round = RoundSnapshot(round_num=current_round_num)
            self.emitted_tips.clear()

        if not self.current_round:
            self.current_round = RoundSnapshot(round_num=current_round_num)

        self.current_round.phase = round_phase

        phase_time_remaining = phase_countdowns.get("phase_ends_in", None)

        # track weapons
        weapons = player.get("weapons", {})
        has_primary, active_type = self._parse_weapons(weapons)
        self.current_round.has_primary = has_primary
        self.current_round.active_weapon_type = active_type

        # track deaths
        prev_health = self.prev_state.get("health", 100)
        cur_health = player_state.get("health", 100)
        if prev_health > 0 and cur_health == 0:
            self.current_round.weapon_at_death = active_type
            if phase_time_remaining is not None:
                elapsed = self.round_duration - phase_time_remaining
            else:
                elapsed = None
            self.current_round.death_time = elapsed
            self.current_round.survived = False

        # once dead this round, stop updating stats from spectated teammates
        if not self.current_round.survived and cur_health > 0:
            self.prev_state = {
                "health": cur_health,
                "round": current_round_num,
                "kills": match_stats.get("kills", 0),
                "deaths": match_stats.get("deaths", 0),
                "team": self.my_team,
            }
            return live_tips, log_tips

        # track kills (per-round fields from player_state)
        self.current_round.kills = player_state.get("round_kills", 0)
        self.current_round.hs_kills = player_state.get("round_killhs", 0)

        # track economy
        self.current_round.equipment_value = player_state.get("equip_value", 0)
        self.current_round.armor = player_state.get("armor", 0)
        money = player_state.get("money", 0)
        self.current_round.team_money = money

        # track bomb plant
        bomb_state = bomb.get("state", "")
        if bomb_state == "planted":
            self.current_round.bomb_planted = True

        late_freezetime = (
            round_phase == "freezetime"
            and phase_time_remaining is not None
            and phase_time_remaining < FREEZETIME_BUY_WINDOW
        )

        # freezetime tips (only after player has had time to buy)
        if late_freezetime and self.rounds:
            last_round = self.rounds[-1]

            # eco discipline: force buying when you should be saving after a loss
            lost_consecutive = sum(
                1 for r in reversed(list(self.rounds)[-3:]) if r.round_win is False
            )
            if (
                last_round.round_win is False
                and lost_consecutive >= 2
                and self.current_round.equipment_value > FORCE_BUY_EQUIP_THRESHOLD
                and "eco_discipline" not in self._last_pattern
            ):
                self._last_pattern["eco_discipline"] = 1
                live_tips.append("Force buy while team is saving — you're breaking the eco.")

            # no armor on anti-eco (round after a win)
            if (
                last_round.round_win is True
                and self.current_round.armor == 0
                and money >= 650
                and "no_armor" not in self.emitted_tips
            ):
                self.emitted_tips.add("no_armor")
                live_tips.append("No armor — buy helmet before upgrading your weapon.")

            # eco round detection
            if (
                last_round.round_win is False
                and self.current_round.equipment_value < ECO_EQUIP_THRESHOLD
                and money < ECO_MONEY_THRESHOLD
                and "eco_round" not in self.emitted_tips
            ):
                self.emitted_tips.add("eco_round")
                live_tips.append("Eco round — play for picks, don't take aim duels.")

            # force buy guidance
            if (
                lost_consecutive >= 2
                and FORCE_EQUIP_LOW <= self.current_round.equipment_value <= FORCE_EQUIP_HIGH
                and "force_buy" not in self.emitted_tips
            ):
                self.emitted_tips.add("force_buy")
                live_tips.append("Force buy — play close angles, make it count.")

        if (
            late_freezetime
            and not self.current_round.has_primary
            and money >= RIFLE_BUY_THRESHOLD
            and self.current_round.equipment_value > SAVE_EQUIP_THRESHOLD
            and "no_primary" not in self.emitted_tips
        ):
            self.emitted_tips.add("no_primary")
            live_tips.append("No primary weapon — you have enough for a rifle.")

        # live tips (during round)
        if round_phase == "live":
            live_tips.extend(self._live_tips(player_state, match_stats, bomb, phase_time_remaining))

        # round over
        if round_phase == "over":
            win_team = round_data.get("win_team", "")
            self.current_round.round_win = win_team == self.my_team
            round_wins = map_data.get("round_wins", {})
            self.current_round.win_method = round_wins.get(str(current_round_num), "")

        self.prev_state = {
            "health": cur_health,
            "round": current_round_num,
            "kills": match_stats.get("kills", 0),
            "deaths": match_stats.get("deaths", 0),
            "team": self.my_team,
        }

        return live_tips, log_tips

    def set_damage_report(self, given: list, taken: list):
        target = self.current_round
        if self.rounds and self.current_round and self.current_round.phase == "freezetime":
            target = self.rounds[-1]
        if target:
            target.damage_given = given
            target.damage_taken = taken

    def _live_tips(
        self,
        player_state: dict,
        match_stats: dict,
        bomb: dict,
        phase_time_remaining: float | None,
    ) -> list[str]:
        tips = []

        cur_health = player_state.get("health", 100)

        # low health warning (only if alive at low hp for a sustained period)
        if 0 < cur_health <= LOW_HP_THRESHOLD:
            now = time.monotonic()
            if self._low_hp_since is None:
                self._low_hp_since = now
            elif now - self._low_hp_since >= LOW_HP_DELAY and "low_hp" not in self.emitted_tips:
                self.emitted_tips.add("low_hp")
                tips.append(f"{cur_health}hp — hold an angle, don't push.")
        else:
            self._low_hp_since = None

        # premature save (T side, lots of time left, alive but no gun)
        if (
            phase_time_remaining is not None
            and phase_time_remaining > SAVE_TIME_THRESHOLD
            and self.my_team == "T"
            and cur_health > 0
            and player_state.get("equip_value", 0) < SAVE_EQUIP_THRESHOLD
            and bomb.get("state", "") != "planted"
            and "premature_save" not in self.emitted_tips
        ):
            self.emitted_tips.add("premature_save")
            secs = int(phase_time_remaining)
            tips.append(f"{secs}s left and you're saving — your gun could still win this.")

        flashed = player_state.get("flashed", 0)
        if flashed > 200 and "flashed_warning" not in self.emitted_tips:
            self.emitted_tips.add("flashed_warning")
            tips.append("Full flash — back off and reposition.")

        # too late to defuse
        bomb_state = bomb.get("state", "")
        raw_countdown = bomb.get("countdown", None)
        try:
            bomb_countdown = float(raw_countdown) if raw_countdown else None
        except (ValueError, TypeError):
            bomb_countdown = None
        if (
            bomb_state == "planted"
            and bomb_countdown is not None
            and self.my_team == "CT"
            and player_state.get("health", 0) > 0
            and "defuse_too_late" not in self.emitted_tips
        ):
            has_kit = player_state.get("defusekit", False)
            required = DEFUSE_TIME_KIT if has_kit else DEFUSE_TIME_NO_KIT
            if bomb_countdown < required:
                self.emitted_tips.add("defuse_too_late")
                tips.append("Too late to defuse — save your weapon.")

        # time pressure (T side, bomb not planted)
        if (
            phase_time_remaining is not None
            and phase_time_remaining < TIME_PRESSURE_THRESHOLD
            and self.my_team == "T"
            and bomb_state != "planted"
            and "time_pressure" not in self.emitted_tips
        ):
            self.emitted_tips.add("time_pressure")
            tips.append("Under 15s — commit to a site or save.")

        # AWP playstyle
        if (
            self.current_round
            and self.current_round.active_weapon_type == "SniperRifle"
            and cur_health > 0
            and "awp_playstyle" not in self.emitted_tips
        ):
            self.emitted_tips.add("awp_playstyle")
            tips.append("AWP out — hold an angle, don't peek.")

        # SMG on gun round
        if (
            self.current_round
            and self.current_round.active_weapon_type == "Submachine Gun"
            and self.current_round.round_num > 3
            and player_state.get("equip_value", 0) > 2000
            and cur_health > 0
            and "smg_warning" not in self.emitted_tips
        ):
            self.emitted_tips.add("smg_warning")
            tips.append("SMG vs rifles — play close, avoid long range.")

        # CT retake: bomb planted, don't solo
        if (
            bomb_state == "planted"
            and self.my_team == "CT"
            and cur_health > 0
            and bomb_countdown is not None
            and bomb_countdown > RETAKE_BOMB_THRESHOLD
            and "retake_wait" not in self.emitted_tips
        ):
            self.emitted_tips.add("retake_wait")
            tips.append("Bomb planted — wait for teammates, don't solo retake.")

        # bomb countdown overlay (both sides, key thresholds only)
        if bomb_state == "planted" and bomb_countdown is not None:
            secs = int(bomb_countdown)
            for threshold in BOMB_COUNTDOWN_THRESHOLDS:
                key = f"bomb_countdown_{threshold}"
                if secs <= threshold and key not in self.emitted_tips:
                    self.emitted_tips.add(key)
                    if self.my_team == "CT":
                        has_kit = player_state.get("defusekit", False)
                        required = DEFUSE_TIME_KIT if has_kit else DEFUSE_TIME_NO_KIT
                        if secs > required:
                            tips.append(f"BOMB: {secs}s — get to it!")
                        else:
                            tips.append(f"BOMB: {secs}s — too late, save your gun.")
                    else:
                        tips.append(f"BOMB: {secs}s")
                    break

        return tips

    PATTERN_COOLDOWN_ROUNDS = 3

    def _emit_pattern(self, key: str, severity: int, msg: str, tips: list[str]):
        current_round = self.rounds[-1].round_num if self.rounds else 0
        cooldown_until = self._pattern_cooldown.get(key, 0)
        if current_round < cooldown_until:
            return
        prev = self._last_pattern.get(key, 0)
        if severity > prev:
            self._last_pattern[key] = severity
            self._pattern_cooldown[key] = current_round + self.PATTERN_COOLDOWN_ROUNDS
            tips.append(msg)

    def _reset_pattern(self, key: str):
        self._last_pattern.pop(key, None)
        self._pattern_cooldown.pop(key, None)

    def _analyze_on_round_end(self) -> list[str]:
        tips = []
        recent = list(self.rounds)[-5:]
        if not recent:
            return tips

        # early death pattern
        early_deaths = [r for r in recent[-3:] if r.death_time is not None and r.death_time < 20]
        if len(early_deaths) >= 2:
            self._emit_pattern(
                "early_death",
                len(early_deaths),
                f"You died early {len(early_deaths)} of the last "
                f"{len(recent[-3:])} rounds. Consider playing passive "
                f"and letting them come to you.",
                tips,
            )
        else:
            self._reset_pattern("early_death")

        last = self.rounds[-1]
        if (
            last.weapon_at_death == "Knife"
            and not last.survived
            and last.death_time is not None
            and last.death_time < 30
        ):
            self._emit_pattern(
                "knife_death",
                1,
                "You died with your knife out — slow down on rotates.",
                tips,
            )
        else:
            self._reset_pattern("knife_death")

        # losing streak
        recent_results = [r.round_win for r in recent[-4:] if r.round_win is not None]
        consecutive_losses = 0
        for w in reversed(recent_results):
            if not w:
                consecutive_losses += 1
            else:
                break
        if consecutive_losses >= 3:
            self._emit_pattern(
                "loss_streak",
                consecutive_losses,
                f"{consecutive_losses} round loss streak. Consider changing your approach — "
                "different site, different timing, or save for a full buy.",
                tips,
            )
        else:
            self._reset_pattern("loss_streak")
            self._reset_pattern("eco_discipline")

        # not getting kills
        zero_kill_rounds = [r for r in recent[-4:] if r.kills == 0 and not r.survived]
        if len(zero_kill_rounds) >= 3:
            self._emit_pattern(
                "no_kills",
                len(zero_kill_rounds),
                "You've died without getting a kill in "
                f"{len(zero_kill_rounds)} of the last 4 rounds. "
                "Play for trades — stick closer to a teammate.",
                tips,
            )
        else:
            self._reset_pattern("no_kills")

        # bomb plant frequency (T pressure on CT rotations)
        total_rounds = len(self.rounds)
        if total_rounds >= 6:
            recent_6 = list(self.rounds)[-6:]
            recent_plants = sum(1 for r in recent_6 if r.bomb_planted)
            if recent_plants >= 4:
                self._emit_pattern(
                    "bomb_pressure",
                    recent_plants,
                    f"They've planted the bomb {recent_plants} of the last 6 rounds "
                    "— rotate faster when you hear the plant.",
                    tips,
                )
            else:
                self._reset_pattern("bomb_pressure")

        # loss method patterns
        recent_losses = [r for r in recent[-4:] if r.round_win is False and r.win_method]
        if len(recent_losses) >= 3:
            method_counts = Counter(r.win_method for r in recent_losses)
            top_method, top_count = method_counts.most_common(1)[0]
            if top_count >= 3:
                if "bomb" in top_method:
                    self._emit_pattern(
                        "loss_method",
                        top_count,
                        f"Lost {top_count} rounds to bomb plants — consider rotating faster.",
                        tips,
                    )
                elif "elimination" in top_method:
                    self._emit_pattern(
                        "loss_method",
                        top_count,
                        f"Lost {top_count} rounds to elimination — "
                        "play more passively and trade together.",
                        tips,
                    )
                elif "time" in top_method:
                    self._emit_pattern(
                        "loss_method",
                        top_count,
                        f"Lost {top_count} rounds to time running out — commit to a site earlier.",
                        tips,
                    )
                else:
                    self._reset_pattern("loss_method")
            else:
                self._reset_pattern("loss_method")
        else:
            self._reset_pattern("loss_method")

        # dying without impact (consecutive loss rounds with 0 kills)
        consecutive_no_impact = 0
        for r in reversed(recent):
            if not r.survived and r.kills == 0 and r.round_win is False:
                consecutive_no_impact += 1
            else:
                break
        if consecutive_no_impact >= 3:
            self._emit_pattern(
                "no_impact",
                consecutive_no_impact,
                "Dying without impact again — wait for support before peeking.",
                tips,
            )
        else:
            self._reset_pattern("no_impact")

        # survival rate
        all_rounds = list(self.rounds)
        if len(all_rounds) >= 6:
            recent_6 = all_rounds[-6:]
            survived_count = sum(1 for r in recent_6 if r.survived)
            if survived_count <= 1:
                self._emit_pattern(
                    "low_survival",
                    6 - survived_count,
                    f"You survived {survived_count} of the last 6 rounds. "
                    "You're dying too much — play for survival, not hero plays.",
                    tips,
                )
            else:
                self._reset_pattern("low_survival")

        if last.damage_given and last.kills == 0:
            hit_count = len(last.damage_given)
            if hit_count >= 3:
                tips.append(f"You hit {hit_count} opponents but finished none — focus fire.")
        for name, dmg, hits in last.damage_given:
            if 90 <= dmg <= 99:
                tips.append(f"{dmg} in {hits} on {name} — one headshot converts that.")
                break
        if len(last.damage_taken) >= 4:
            tips.append(
                f"You took damage from {len(last.damage_taken)} players — "
                "you were exposed to too many angles."
            )

        return tips

    def _format_round_stats(self, match_stats: dict) -> str:
        last = self.rounds[-1]
        kills = match_stats.get("kills", 0)
        assists = match_stats.get("assists", 0)
        deaths = match_stats.get("deaths", 0)
        score = match_stats.get("score", 0)
        mvps = match_stats.get("mvps", 0)

        total_kills = sum(r.kills for r in self.rounds)
        total_hs = sum(r.hs_kills for r in self.rounds)
        hs_pct = (total_hs / total_kills * 100) if total_kills > 0 else 0

        result = "W" if last.round_win else "L" if last.round_win is False else "?"
        survived = "alive" if last.survived else "dead"

        comment = self._round_comment(last)

        parts = [
            f"R{last.round_num} {result}",
            f"{last.kills}K/{last.hs_kills}HS ({survived})",
            f"Match: {kills}/{assists}/{deaths} ({hs_pct:.0f}% HS)",
            f"Score:{score} MVPs:{mvps}",
            comment,
        ]
        return " | ".join(parts)

    def _round_comment(self, r: RoundSnapshot) -> str:
        completed = list(self.rounds)

        if r.kills >= 3 and r.survived:
            return "Dominant round."
        if r.kills >= 3:
            return "Big impact even though you went down."
        if r.round_win and r.survived and r.kills >= 1:
            return "Solid round."
        if r.round_win and r.kills == 0 and r.survived:
            return "Stayed alive, that counts."
        if r.round_win:
            return "Got the W."
        if not r.survived and r.kills == 0 and r.death_time is not None and r.death_time < 20:
            return "Rough — died early with no impact."
        if not r.survived and r.kills == 0:
            recent_zero = sum(1 for rd in completed[-5:] if rd.kills == 0 and not rd.survived)
            if recent_zero >= 3:
                return "Still no kills — might be time to change positions entirely."
            return "No kills that round — try to get a trade next time."
        if not r.survived and r.kills >= 1:
            recent_trade_deaths = sum(
                1 for rd in completed[-5:] if rd.kills >= 1 and not rd.survived
            )
            if recent_trade_deaths >= 3 and len(completed) >= 5:
                return "Trading but never surviving — try playing second in."
            return "Got a pick before going down."
        return "On to the next one."

    def _parse_weapons(self, weapons: dict) -> tuple[bool, str]:
        has_primary = False
        active_type = ""
        for w in weapons.values():
            if not isinstance(w, dict):
                continue
            wtype = w.get("type", "")
            if wtype in PRIMARY_TYPES:
                has_primary = True
            if w.get("state") == "active":
                active_type = wtype
        return has_primary, active_type
