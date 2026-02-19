import sys
import threading
import time
from collections import deque

APP_NAME = "cs2whine"


def _show_windows_toast(title: str, msg: str):
    from windows_toasts import Toast, ToastAudio, WindowsToaster

    toaster = WindowsToaster(title)
    toast = Toast()
    toast.text_fields = [msg]
    toast.audio = ToastAudio(silent=True)
    toast.on_dismissed = lambda _: toaster.remove_toast(toast)
    toaster.show_toast(toast)


class Notifier:
    def __init__(self, rate_limit: float = 8.0, overlay=None):
        self.rate_limit = rate_limit
        self.overlay = overlay
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
                print(f"\n[NOTIFICATION ERROR] {e}", flush=True)

            time.sleep(0.5)

    def _show(self, body: str):
        if self.overlay:
            self.overlay.show_tip(body)
        if sys.platform == "win32":
            try:
                _show_windows_toast(APP_NAME, body[:256])
            except Exception as e:
                print(f"\n[TOAST FAILED] {e}", flush=True)
        else:
            print(f"\n[NOTIFICATION] {body}", flush=True)
