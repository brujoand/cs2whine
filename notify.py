import subprocess
import sys
import threading
import time
from collections import deque

APP_NAME = "CS2 Coach"

# fmt: off
PS_TEMPLATE = (
    "[Windows.UI.Notifications.ToastNotificationManager,"
    " Windows.UI.Notifications, ContentType = WindowsRuntime] > $null\n"
    "[Windows.Data.Xml.Dom.XmlDocument,"
    " Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null\n"
    '\n$Template = @"\n'
    '<toast duration="short">\n'
    "    <visual>\n"
    '        <binding template="ToastGeneric">\n'
    "            <text>{title}</text>\n"
    "            <text>{msg}</text>\n"
    "        </binding>\n"
    "    </visual>\n"
    '    <audio silent="true" />\n'
    "</toast>\n"
    '"@\n'
    "\n"
    "$Xml = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
    "$Xml.LoadXml($Template)\n"
    "$Toast = [Windows.UI.Notifications.ToastNotification]::new($Xml)\n"
    "$Notifier = [Windows.UI.Notifications.ToastNotificationManager]"
    '::CreateToastNotifier("{app_id}")\n'
    "$Notifier.Show($Toast)\n"
)
# fmt: on


def _escape_xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _show_windows_toast(title: str, msg: str):
    script = PS_TEMPLATE.format(
        title=_escape_xml(title),
        msg=_escape_xml(msg),
        app_id=APP_NAME,
    )
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        timeout=10,
        startupinfo=si,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"PowerShell exit {result.returncode}: {stderr}")


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
                print(f"[NOTIFICATION ERROR] {e}", flush=True)

            time.sleep(0.5)

    def _show(self, body: str):
        if sys.platform == "win32":
            try:
                _show_windows_toast("CS2 Coach", body[:256])
            except Exception as e:
                print(f"\n[TOAST FAILED] {e}", flush=True)
        else:
            print(f"\n[NOTIFICATION] {body}", flush=True)
