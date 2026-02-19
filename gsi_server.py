import logging
import threading

from flask import Flask, request

import config
from coaching import CoachingEngine
from notify import Notifier
from overlay import App
from setup_gsi import install_gsi_config
from updater import check_for_update

app = Flask(__name__)
coach = CoachingEngine()
cfg = config.load()

gui = App()
notifier = Notifier(rate_limit=cfg.get("notification_rate_limit", 8.0), overlay=gui.overlay)


request_count = 0


@app.route("/", methods=["POST"])
def gsi_callback():
    global request_count
    data = request.get_json(silent=True)
    if not data:
        return "no data", 400

    gui.set_last_gsi(data)

    request_count += 1
    if request_count == 1:
        gui.set_status("Connected")

    map_data = data.get("map", {})
    round_data = data.get("round", {})
    player = data.get("player", {})
    round_num = map_data.get("round", "?")
    phase = round_data.get("phase", map_data.get("phase", "?"))
    team = player.get("team", "?")
    health = player.get("state", {}).get("health", "?")
    gui.set_status(f"[R{round_num}] {phase} | {team} | hp:{health}")

    live_tips, log_tips = coach.process(data)

    if coach.pending_round_stats:
        gui.log(f"--- {coach.pending_round_stats}")
        coach.pending_round_stats = None

    for tip in log_tips:
        gui.log(f">>> {tip}")

    for tip in live_tips:
        gui.log(f">>> {tip}")
        notifier.send(tip)

    return "ok"


def main():
    check_for_update()
    install_gsi_config()
    port = cfg["port"]
    gui.log(f"cs2whine listening on http://localhost:{port}")
    gui.log("Start CS2 and play a match. Tips will appear as overlay notifications.")
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    flask_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False),
        daemon=True,
    )
    flask_thread.start()
    gui.run()


if __name__ == "__main__":
    main()
