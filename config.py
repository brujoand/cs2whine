import json
import os
import sys


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)


CONFIG_PATH = os.path.join(_base_dir(), "config.json")

DEFAULTS = {
    "port": 3001,
    "notification_rate_limit": 8.0,
}


def load() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            user = json.load(f)
        return {**DEFAULTS, **user}
    return dict(DEFAULTS)
