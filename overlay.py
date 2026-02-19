import sys
import threading


class Overlay:
    def __init__(self):
        self._root = None
        self._label = None
        self._clear_job = None

        if sys.platform != "win32":
            return

        import ctypes
        import tkinter as tk

        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        GWL_EXSTYLE = -20

        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg="black")
        root.wm_attributes("-transparentcolor", "black")

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        win_w = 800
        win_h = 60
        x = (screen_w - win_w) // 2
        y = screen_h - 200
        root.geometry(f"{win_w}x{win_h}+{x}+{y}")

        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        )

        label = tk.Label(
            root,
            text="",
            bg="black",
            fg="#00FF00",
            font=("Consolas", 18, "bold"),
            wraplength=780,
            justify="center",
        )
        label.place(relx=0.5, rely=0.5, anchor="center")

        self._root = root
        self._label = label

    def show_tip(self, text: str, duration: float = 5.0):
        if self._root is None:
            print(f"\n[OVERLAY] {text}", flush=True)
            return
        self._root.after(0, self._display, text, duration)

    def _display(self, text: str, duration: float):
        if self._clear_job is not None:
            self._root.after_cancel(self._clear_job)
        self._label.config(text=text)
        self._clear_job = self._root.after(int(duration * 1000), self._clear)

    def _clear(self):
        self._label.config(text="")
        self._clear_job = None

    def run(self):
        if self._root is None:
            threading.Event().wait()
            return
        self._root.mainloop()
