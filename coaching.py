import time
from collections import deque
from dataclasses import dataclass

DEFUSE_TIME_KIT = 5.0
DEFUSE_TIME_NO_KIT = 10.0
TIME_PRESSURE_THRESHOLD = 15.0
LOW_HP_THRESHOLD = 35
SAVE_TIME_THRESHOLD = 60.0
SAVE_EQUIP_THRESHOLD = 500
FORCE_BUY_EQUIP_THRESHOLD = 2000
FREEZETIME_BUY_WINDOW = 10.0
LOW_HP_DELAY = 2.0


@dataclass
class RoundSnapshot:
    round_num: int
    phase: str = ""
    death_time: float | None = None
    death_position: tuple | None = None
    kills: int = 0
    hs_kills: int = 0
    equipment_value: int = 0
    armor: int = 0
    team_money: int = 0
    survived: bool = True
    bomb_planted_site: str | None = None
    round_win: bool | None = None


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
        self.pending_round_stats: str | None = None
        self._low_hp_since: float | None = None
        self._prev_ct_score: int = 0
        self._prev_t_score: int = 0

    def process(self, data: dict) -> list[str]:
        tips = []

        map_data = data.get("map", {})
        player = data.get("player", {})
        player_state = player.get("state", {})
        match_stats = player.get("match_stats", {})
        round_data = data.get("round", {})
        bomb = data.get("bomb", {})
        phase_countdowns = data.get("phase_countdowns", {})

        if not player or not map_data:
            return tips

        provider_steam = data.get("provider", {}).get("steamid", "")
        player_steam = player.get("steamid", "")
        if provider_steam and player_steam and provider_steam != player_steam:
            return tips

        current_round_num = map_data.get("round", 0)
        round_phase = round_data.get("phase", "")
        map_phase = map_data.get("phase", "")
        self.match_map = map_data.get("name", "")
        new_team = player.get("team", "")
        if new_team != self.my_team:
            self._last_pattern.clear()
        self.my_team = new_team

        if map_phase == "warmup":
            return tips

        if current_round_num == 0:
            return tips

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
                tips.extend(self._analyze_on_round_end())
                self.pending_round_stats = self._format_round_stats(match_stats)
            self._prev_ct_score = ct_score
            self._prev_t_score = t_score
            self.current_round = RoundSnapshot(round_num=current_round_num)
            self.emitted_tips.clear()

        if not self.current_round:
            self.current_round = RoundSnapshot(round_num=current_round_num)

        self.current_round.phase = round_phase

        phase_time_remaining = phase_countdowns.get("phase_ends_in", None)

        # track deaths
        prev_health = self.prev_state.get("health", 100)
        cur_health = player_state.get("health", 100)
        if prev_health > 0 and cur_health == 0:
            if phase_time_remaining is not None:
                elapsed = self.round_duration - phase_time_remaining
            else:
                elapsed = None
            pos = data.get("player", {}).get("position", "")
            self.current_round.death_time = elapsed
            self.current_round.survived = False
            if pos:
                try:
                    coords = tuple(float(x) for x in pos.split(", "))
                    self.current_round.death_position = coords
                except (ValueError, AttributeError):
                    pass

        # track kills (per-round fields from player_state)
        self.current_round.kills = player_state.get("round_kills", 0)
        self.current_round.hs_kills = player_state.get("round_killhs", 0)

        # track economy
        self.current_round.equipment_value = player_state.get("equip_value", 0)
        self.current_round.armor = player_state.get("armor", 0)
        money = player_state.get("money", 0)
        self.current_round.team_money = money

        # track bomb
        bomb_state = bomb.get("state", "")
        if bomb_state == "planted":
            bomb_pos = bomb.get("position", "")
            self.current_round.bomb_planted_site = self._pos_to_site(bomb_pos)

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
                tips.append("Force buy while team is saving — you're breaking the eco.")

            # no armor on anti-eco (round after a win)
            if (
                last_round.round_win is True
                and self.current_round.armor == 0
                and money >= 650
                and "no_armor" not in self.emitted_tips
            ):
                self.emitted_tips.add("no_armor")
                tips.append("No armor — buy helmet before upgrading your weapon.")

        # live tips (during round)
        if round_phase == "live":
            tips.extend(self._live_tips(player_state, match_stats, bomb, phase_time_remaining))

        # round over
        if round_phase == "over":
            win_team = round_data.get("win_team", "")
            self.current_round.round_win = win_team == self.my_team

        self.prev_state = {
            "health": cur_health,
            "round": current_round_num,
            "kills": match_stats.get("kills", 0),
            "deaths": match_stats.get("deaths", 0),
            "team": self.my_team,
        }

        return tips

    def _live_tips(
        self,
        player_state: dict,
        match_stats: dict,
        bomb: dict,
        phase_time_remaining: float | None,
    ) -> list[str]:
        tips = []

        cur_health = player_state.get("health", 100)
        round_kills = player_state.get("round_kills", 0)

        if round_kills >= 3 and f"multikill_{round_kills}" not in self.emitted_tips:
            self.emitted_tips.add(f"multikill_{round_kills}")
            labels = {3: "Triple kill", 4: "Quad kill", 5: "ACE"}
            label = labels.get(round_kills, f"{round_kills}K")
            tips.append(f"{label}! Nice.")

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
            recent_flashes = sum(1 for r in list(self.rounds)[-3:] if not r.survived)
            if recent_flashes >= 2:
                tips.append(
                    "You keep getting flashed and dying. "
                    "Try holding a different angle or playing further back."
                )

        # too late to defuse
        bomb_state = bomb.get("state", "")
        bomb_countdown = bomb.get("countdown", None)
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

        return tips

    def _emit_pattern(self, key: str, severity: int, msg: str, tips: list[str]):
        prev = self._last_pattern.get(key, 0)
        if severity > prev:
            self._last_pattern[key] = severity
            tips.append(msg)

    def _reset_pattern(self, key: str):
        self._last_pattern.pop(key, None)

    def _analyze_on_round_end(self) -> list[str]:
        tips = []
        recent = list(self.rounds)[-5:]
        if not recent:
            return tips

        last = recent[-1]

        # positive: win streak
        recent_wins = [r for r in recent[-3:] if r.round_win is True]
        if len(recent_wins) >= 3:
            self._emit_pattern(
                "win_streak", len(recent_wins), "3 wins in a row — keep it up.", tips
            )

        # positive: consistent fragger
        high_kill_rounds = [r for r in recent[-3:] if r.kills >= 2]
        if len(high_kill_rounds) >= 3:
            self._emit_pattern(
                "hot_streak",
                len(high_kill_rounds),
                "2+ kills every round for the last 3 — you're on fire.",
                tips,
            )

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

        # repeated death location
        death_positions = [r.death_position for r in recent[-4:] if r.death_position]
        if len(death_positions) >= 2:
            clusters = self._find_clusters(death_positions, threshold=500)
            if clusters:
                self._emit_pattern(
                    "death_location",
                    len(clusters),
                    "You keep dying in the same area. "
                    "They probably have it locked down — try a different route.",
                    tips,
                )
            else:
                self._reset_pattern("death_location")
        else:
            self._reset_pattern("death_location")

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

        # eco awareness
        last = recent[-1]
        if last.equipment_value < 2000 and last.round_win is False:
            tips.append(
                "Low equipment value last round. Coordinate an eco or force buy with the team."
            )

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

        # bomb plant patterns (tracking enemy tendencies)
        bomb_sites = [r.bomb_planted_site for r in self.rounds if r.bomb_planted_site]
        if len(bomb_sites) >= 4:
            last_4 = bomb_sites[-4:]
            from collections import Counter

            site_counts = Counter(last_4)
            dominant = site_counts.most_common(1)[0]
            if dominant[1] >= 3:
                self._emit_pattern(
                    "bomb_site",
                    dominant[1],
                    f"They've planted on {dominant[0]} site "
                    f"{dominant[1]} of the last 4 rounds. "
                    f"Consider stacking or rotating earlier.",
                    tips,
                )
            else:
                self._reset_pattern("bomb_site")
        else:
            self._reset_pattern("bomb_site")

        # dying without impact (consecutive rounds dying with 0 kills)
        consecutive_no_impact = 0
        for r in reversed(recent):
            if not r.survived and r.kills == 0:
                consecutive_no_impact += 1
            else:
                break
        if consecutive_no_impact >= 2:
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

        # going cold
        if len(all_rounds) >= 8:
            match_avg = sum(r.kills for r in all_rounds) / len(all_rounds)
            recent_5 = all_rounds[-5:]
            recent_kills = sum(r.kills for r in recent_5)
            recent_avg = recent_kills / 5
            if match_avg > 0.5 and recent_avg < match_avg * 0.5:
                self._emit_pattern(
                    "going_cold",
                    1,
                    f"You're going cold — {recent_kills} kills in the last "
                    f"5 rounds vs your match average of {match_avg:.1f}/round. "
                    "Mix up your approach.",
                    tips,
                )
            else:
                self._reset_pattern("going_cold")

        return tips

    def _find_clusters(self, positions: list[tuple], threshold: float) -> list[tuple]:
        clusters = []
        for i, p1 in enumerate(positions):
            for p2 in positions[i + 1 :]:
                dist = sum((a - b) ** 2 for a, b in zip(p1, p2)) ** 0.5
                if dist < threshold:
                    clusters.append((p1, p2))
        return clusters

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
            if recent_trade_deaths >= 3:
                return "Trading but never surviving — try playing second in."
            return "Got a pick before going down."
        return "On to the next one."

    def _pos_to_site(self, pos_str: str) -> str | None:
        if not pos_str:
            return None
        # rough A/B classification based on map geometry
        # this is a simplification — proper implementation needs per-map data
        try:
            coords = [float(x) for x in pos_str.split(", ")]
        except (ValueError, AttributeError):
            return None
        # placeholder: return generic site label
        # TODO: add per-map bombsite coordinate ranges
        return "A" if coords[0] > 0 else "B"
