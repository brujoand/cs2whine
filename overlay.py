import sys
import tkinter as tk


class Overlay:
    def __init__(self, root: tk.Tk):
        self._root = root
        self._window = None
        self._label = None
        self._clear_job = None
        self._enabled = True

        if sys.platform != "win32":
            return

        import ctypes

        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        GWL_EXSTYLE = -20

        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="black")
        win.wm_attributes("-transparentcolor", "black")

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        win_w = 800
        win_h = 60
        x = (screen_w - win_w) // 2
        y = screen_h - 200
        win.geometry(f"{win_w}x{win_h}+{x}+{y}")

        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        )

        label = tk.Label(
            win,
            text="",
            bg="black",
            fg="#00FF00",
            font=("Consolas", 18, "bold"),
            wraplength=780,
            justify="center",
        )
        label.place(relx=0.5, rely=0.5, anchor="center")

        self._window = win
        self._label = label

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if self._window:
            if enabled:
                self._window.deiconify()
            else:
                self._window.withdraw()
                self._label.config(text="")

    def show_tip(self, text: str, duration: float = 5.0):
        if not self._enabled:
            return
        if self._window is None:
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


class App:
    def __init__(self):
        self._root = tk.Tk()
        self._root.title("cs2whine")
        self._root.geometry("620x400")
        self._root.configure(bg="#1e1e1e")

        top_frame = tk.Frame(self._root, bg="#1e1e1e")
        top_frame.pack(fill="x", padx=8, pady=(8, 0))

        self._overlay_var = tk.BooleanVar(value=True)
        self._overlay_cb = tk.Checkbutton(
            top_frame,
            text="Overlay",
            variable=self._overlay_var,
            command=self._toggle_overlay,
            bg="#1e1e1e",
            fg="#cccccc",
            selectcolor="#333333",
            activebackground="#1e1e1e",
            activeforeground="#cccccc",
            font=("Consolas", 10),
        )
        self._overlay_cb.pack(side="left")

        self._status_label = tk.Label(
            top_frame,
            text="Waiting for CS2...",
            bg="#1e1e1e",
            fg="#888888",
            font=("Consolas", 10),
        )
        self._status_label.pack(side="right")

        log_frame = tk.Frame(self._root, bg="#1e1e1e")
        log_frame.pack(fill="both", expand=True, padx=8, pady=8)

        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")

        self._log_text = tk.Text(
            log_frame,
            bg="#0e0e0e",
            fg="#00cc00",
            font=("Consolas", 10),
            wrap="word",
            state="disabled",
            yscrollcommand=scrollbar.set,
            borderwidth=0,
            highlightthickness=0,
        )
        self._log_text.pack(fill="both", expand=True)
        scrollbar.config(command=self._log_text.yview)

        self.overlay = Overlay(self._root)

    def _toggle_overlay(self):
        self.overlay.set_enabled(self._overlay_var.get())

    def log(self, text: str):
        self._root.after(0, self._append_log, text)

    def set_status(self, text: str):
        self._root.after(0, self._status_label.config, {"text": text})

    def _append_log(self, text: str):
        self._log_text.config(state="normal")
        self._log_text.insert("end", text + "\n")
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    def run(self):
        self._root.mainloop()
