import tkinter as tk
from interface.styling import *
from datetime import datetime
import queue

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

    def add_log(self, level: str, source: str, lineno: int, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        log_line = f"{timestamp} - {level.upper():<5} - {source}:{lineno} - {message}\n"
        self.queue.put(log_line)

    def _poll_queue(self):
        while not self.queue.empty():
            msg = self.queue.get()
            self._logging_text.configure(state=tk.NORMAL)
            self._logging_text.insert("1.0", msg)
            self._logging_text.configure(state=tk.DISABLED)
        self.after(100, self._poll_queue)
