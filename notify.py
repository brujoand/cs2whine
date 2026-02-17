import sys
import threading
import time
from collections import deque

if sys.platform == "win32":
    from winotify import Notification, audio

APP_NAME = "CS2 Coach"


class Notifier:
    def __init__(self, rate_limit: float = 8.0):
        self.rate_limit = rate_limit
        self.last_sent = 0.0
        self.queue: deque[str] = deque(maxlen=10)
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._drain, daemon=True)
        self._worker.start()

    def send(self, tip: str):
        with self._lock:
            self.queue.append(tip)

    def _drain(self):
        while True:
            try:
                batch = []
                with self._lock:
                    while self.queue:
                        batch.append(self.queue.popleft())

                if batch:
                    now = time.time()
                    wait = self.rate_limit - (now - self.last_sent)
                    if wait > 0:
                        time.sleep(wait)

                    msg = "\n".join(batch)
                    self._show(msg)
                    self.last_sent = time.time()
            except Exception as e:
                print(f"[NOTIFICATION ERROR] drain: {e}", flush=True)

            time.sleep(0.5)

    def _show(self, body: str):
        if sys.platform == "win32":
            try:
                toast = Notification(
                    app_id=APP_NAME,
                    title="CS2 Coach",
                    msg=body[:256],
                    duration="short",
                )
                toast.set_audio(audio.Default, loop=False)
                toast.show()
            except Exception as e:
                print(f"[NOTIFICATION ERROR] {e}", flush=True)
        else:
            print(f"[NOTIFICATION] {body}", flush=True)
