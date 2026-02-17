from collections import deque
from dataclasses import dataclass

DEFUSE_TIME_KIT = 5.0
DEFUSE_TIME_NO_KIT = 10.0
KIT_COST = 400
TIME_PRESSURE_THRESHOLD = 15.0


@dataclass
class RoundSnapshot:
    round_num: int
    phase: str = ""
    death_time: float | None = None
    death_position: tuple | None = None
    kills: int = 0
    hs_kills: int = 0
    equipment_value: int = 0
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

        current_round_num = map_data.get("round", 0)
        round_phase = round_data.get("phase", "")
        map_phase = map_data.get("phase", "")
        self.match_map = map_data.get("name", "")
        self.my_team = player.get("team", "")

        if map_phase == "warmup":
            return tips

        # new round started
        if round_phase == "freezetime" and (
            self.current_round is None or self.current_round.round_num != current_round_num
        ):
            if self.current_round:
                self.rounds.append(self.current_round)
                tips.extend(self._analyze_on_round_end())
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
        money = player_state.get("money", 0)
        self.current_round.team_money = money

        # track bomb
        bomb_state = bomb.get("state", "")
        if bomb_state == "planted":
            bomb_pos = bomb.get("position", "")
            self.current_round.bomb_planted_site = self._pos_to_site(bomb_pos)

        # defuse kit reminder (freezetime or live, CT side)
        if (
            round_phase in ("freezetime", "live")
            and self.my_team == "CT"
            and not player_state.get("defusekit", False)
            and player_state.get("money", 0) >= KIT_COST
            and "kit_reminder" not in self.emitted_tips
        ):
            self.emitted_tips.add("kit_reminder")
            tips.append("You can afford a kit — buy one.")

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
        if len(recent) < 2:
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

        return tips

    def _find_clusters(self, positions: list[tuple], threshold: float) -> list[tuple]:
        clusters = []
        for i, p1 in enumerate(positions):
            for p2 in positions[i + 1 :]:
                dist = sum((a - b) ** 2 for a, b in zip(p1, p2)) ** 0.5
                if dist < threshold:
                    clusters.append((p1, p2))
        return clusters

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
