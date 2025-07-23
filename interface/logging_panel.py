import tkinter as tk
from interface.styling import *
from datetime import datetime
import queue
import re

# Regex to parse tracking logs
TRACK_RE = re.compile(
    r"Tracking\s+([A-Za-z0-9]+).*?Buy:\s*\$([0-9.eE+-]+).*?Current:\s*\$([0-9.eE+-]+).*?Peak:\s*\$([0-9.eE+-]+).*?TP:\s*\$([0-9.eE+-]+).*?TSL:\s*\$([0-9.eE+-]+).*?Change:\s*([-\d.]+)%",
    re.IGNORECASE,
)

class LoggingPanel(tk.Frame):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        kwargs.setdefault("bg", BG_COLOR)

        # Scrollable Text Widget
        self._logging_text = tk.Text(
            self,
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg=BG_COLOR,
            fg=FG_COLOR_STEEL_BLUE,
            font=("Courier New", 10),
            insertbackground=FG_COLOR_STEEL_BLUE,
            relief=tk.FLAT,
            borderwidth=0
        )
        self._logging_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = tk.Scrollbar(self, command=self._logging_text.yview, bg=BG_COLOR, troughcolor=BG_COLOR)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._logging_text.config(yscrollcommand=scrollbar.set)

        # Message Queue
        self.queue = queue.Queue()
        self.after(100, self._poll_queue)

    def add_log(self, msg: str):
        """Add a log message (thread-safe if needed)."""
        clean_msg = msg.strip()
        if "Tracking" in clean_msg:
            clean_msg = self._format_tracking_message(clean_msg)
        clean_msg += "\n"

        self._logging_text.configure(state=tk.NORMAL)
        self._logging_text.insert("end", clean_msg)
        self._logging_text.see("end")
        self._logging_text.configure(state=tk.DISABLED)

    def queue_put(self, msg: str):
        self.queue.put(msg)

    def _insert_text(self, msg: str):
        clean_msg = msg.strip()
        if "Tracking" in clean_msg:
            clean_msg = self._format_tracking_message(clean_msg)
        clean_msg += "\n"

        self._logging_text.configure(state=tk.NORMAL)
        self._logging_text.insert("end", clean_msg)
        self._logging_text.see("end")
        self._logging_text.configure(state=tk.DISABLED)

    def _poll_queue(self):
        while not self.queue.empty():
            msg = self.queue.get()
            self._insert_text(msg)
        self.after(100, self._poll_queue)

    def _format_tracking_message(self, msg: str) -> str:
        match = TRACK_RE.search(msg)
        if not match:
            return msg  # fallback if parsing fails

        token, tp, tsl, change = match.groups()

        # Compact single-line formatting
        return (f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"🔎 {token:<12}  "
                f"TP: {float(tp):<10.8f}  "
                f"TSL: {float(tsl):<10.8f}  "
                f"Change: {change}%")

