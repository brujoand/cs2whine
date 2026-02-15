from dataclasses import dataclass, field
from collections import deque
import time


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
        self.round_start_time: float = 0
        self.match_map: str = ""
        self.my_team: str = ""
        self.emitted_tips: set = set()

    def process(self, data: dict) -> list[str]:
        tips = []

        map_data = data.get("map", {})
        player = data.get("player", {})
        player_state = player.get("state", {})
        match_stats = player.get("match_stats", {})
        round_data = data.get("round", {})
        bomb = data.get("bomb", {})

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
            self.current_round is None
            or self.current_round.round_num != current_round_num
        ):
            if self.current_round:
                self.rounds.append(self.current_round)
                tips.extend(self._analyze_on_round_end())
            self.current_round = RoundSnapshot(round_num=current_round_num)
            self.round_start_time = time.time()
            self.emitted_tips.clear()

        if not self.current_round:
            self.current_round = RoundSnapshot(round_num=current_round_num)
            self.round_start_time = time.time()

        self.current_round.phase = round_phase

        # track deaths
        prev_health = self.prev_state.get("health", 100)
        cur_health = player_state.get("health", 100)
        if prev_health > 0 and cur_health == 0:
            elapsed = time.time() - self.round_start_time
            pos = data.get("player", {}).get("position", "")
            self.current_round.death_time = elapsed
            self.current_round.survived = False
            if pos:
                try:
                    coords = tuple(float(x) for x in pos.split(", "))
                    self.current_round.death_position = coords
                except (ValueError, AttributeError):
                    pass

        # track kills
        self.current_round.kills = match_stats.get("kills", 0)
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

        # live tips (during round)
        if round_phase == "live":
            tips.extend(self._live_tips(player_state, match_stats))

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

    def _live_tips(self, player_state: dict, match_stats: dict) -> list[str]:
        tips = []

        flashed = player_state.get("flashed", 0)
        if flashed > 200 and "flashed_warning" not in self.emitted_tips:
            self.emitted_tips.add("flashed_warning")
            recent_flashes = sum(
                1 for r in list(self.rounds)[-3:] if not r.survived
            )
            if recent_flashes >= 2:
                tips.append(
                    "You keep getting flashed and dying. "
                    "Try holding a different angle or playing further back."
                )

        return tips

    def _analyze_on_round_end(self) -> list[str]:
        tips = []
        recent = list(self.rounds)[-5:]
        if len(recent) < 2:
            return tips

        # early death pattern
        early_deaths = [
            r for r in recent[-3:] if r.death_time and r.death_time < 20
        ]
        if len(early_deaths) >= 2:
            tips.append(
                f"You died early {len(early_deaths)} of the last "
                f"{len(recent[-3:])} rounds. Consider playing passive "
                f"and letting them come to you."
            )

        # repeated death location
        death_positions = [r.death_position for r in recent[-4:] if r.death_position]
        if len(death_positions) >= 2:
            clusters = self._find_clusters(death_positions, threshold=500)
            if clusters:
                tips.append(
                    "You keep dying in the same area. "
                    "They probably have it locked down — try a different route."
                )

        # losing streak
        recent_results = [r.round_win for r in recent[-4:] if r.round_win is not None]
        if len(recent_results) >= 3 and all(not w for w in recent_results[-3:]):
            tips.append(
                "3 round loss streak. Consider changing your approach — "
                "different site, different timing, or save for a full buy."
            )

        # eco awareness
        last = recent[-1]
        if last.equipment_value < 2000 and last.round_win is False:
            tips.append(
                "Low equipment value last round. "
                "Coordinate an eco or force buy with the team."
            )

        # not getting kills
        zero_kill_rounds = [r for r in recent[-4:] if r.kills == 0 and not r.survived]
        if len(zero_kill_rounds) >= 3:
            tips.append(
                "You've died without getting a kill in "
                f"{len(zero_kill_rounds)} of the last 4 rounds. "
                "Play for trades — stick closer to a teammate."
            )

        # bomb plant patterns (tracking enemy tendencies)
        bomb_sites = [
            r.bomb_planted_site for r in self.rounds if r.bomb_planted_site
        ]
        if len(bomb_sites) >= 4:
            last_4 = bomb_sites[-4:]
            from collections import Counter

            site_counts = Counter(last_4)
            dominant = site_counts.most_common(1)[0]
            if dominant[1] >= 3:
                tips.append(
                    f"They've planted on {dominant[0]} site "
                    f"{dominant[1]} of the last 4 rounds. "
                    f"Consider stacking or rotating earlier."
                )

        return tips

    def _find_clusters(
        self, positions: list[tuple], threshold: float
    ) -> list[tuple]:
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
