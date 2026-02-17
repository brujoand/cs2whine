import logging
import sys

from flask import Flask, request

import config
from coaching import CoachingEngine
from notify import Notifier
from setup_gsi import install_gsi_config
from updater import check_for_update

app = Flask(__name__)
coach = CoachingEngine()
cfg = config.load()

notifier = Notifier(rate_limit=cfg.get("notification_rate_limit", 8.0))


request_count = 0


@app.route("/", methods=["POST"])
def gsi_callback():
    global request_count
    data = request.get_json(silent=True)
    if not data:
        return "no data", 400

    request_count += 1
    if request_count == 1:
        print("Receiving GSI data from CS2.", flush=True)

    map_data = data.get("map", {})
    round_data = data.get("round", {})
    player = data.get("player", {})
    round_num = map_data.get("round", "?")
    phase = round_data.get("phase", map_data.get("phase", "?"))
    team = player.get("team", "?")
    health = player.get("state", {}).get("health", "?")
    print(f"\r[R{round_num}] {phase} | {team} | hp:{health}", end="", flush=True)

    tips = coach.process(data)
    for tip in tips:
        print(f"\n>>> {tip}", flush=True)
        notifier.send(tip)

    return "ok"


def main():
    check_for_update()
    install_gsi_config()
    port = cfg["port"]
    print(f"cs2whine listening on http://localhost:{port}", flush=True)
    print("Start CS2 and play a match. Tips will appear as notifications.", flush=True)
    sys.stdout.reconfigure(line_buffering=True)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
