import os
import re
import threading
import time
from dataclasses import dataclass, field

DMG_GIVEN_RE = re.compile(r'Damage Given to "(.+?)" - (\d+) in (\d+) hits?')
DMG_TAKEN_RE = re.compile(r'Damage Taken from "(.+?)" - (\d+) in (\d+) hits?')


@dataclass
class DamageReport:
    given: list[tuple[str, int, int]] = field(default_factory=list)
    taken: list[tuple[str, int, int]] = field(default_factory=list)


class ConsoleLogParser:
    def __init__(self, log_path: str):
        self._path = log_path
        self._offset = 0
        self._lock = threading.Lock()
        self._pending: DamageReport | None = None
        self._building: DamageReport | None = None

    def start(self):
        if not os.path.isfile(self._path):
            self._offset = 0
        else:
            self._offset = os.path.getsize(self._path)
        t = threading.Thread(target=self._tail, daemon=True)
        t.start()

    def _tail(self):
        while True:
            try:
                if not os.path.isfile(self._path):
                    time.sleep(1.0)
                    continue
                size = os.path.getsize(self._path)
                if size < self._offset:
                    self._offset = 0
                if size > self._offset:
                    with open(self._path, encoding="utf-8", errors="replace") as f:
                        f.seek(self._offset)
                        new_text = f.read()
                        self._offset = f.tell()
                    self._parse(new_text)
            except OSError:
                pass
            time.sleep(0.5)

    def _parse(self, text: str):
        for line in text.splitlines():
            gm = DMG_GIVEN_RE.search(line)
            if gm:
                if self._building is None:
                    self._building = DamageReport()
                self._building.given.append((gm.group(1), int(gm.group(2)), int(gm.group(3))))
                continue
            tm = DMG_TAKEN_RE.search(line)
            if tm:
                if self._building is None:
                    self._building = DamageReport()
                self._building.taken.append((tm.group(1), int(tm.group(2)), int(tm.group(3))))
                continue
            if self._building and (self._building.given or self._building.taken):
                with self._lock:
                    self._pending = self._building
                self._building = None

        if self._building and (self._building.given or self._building.taken):
            with self._lock:
                self._pending = self._building
            self._building = None

    def take_report(self) -> DamageReport | None:
        with self._lock:
            r = self._pending
            self._pending = None
            return r
