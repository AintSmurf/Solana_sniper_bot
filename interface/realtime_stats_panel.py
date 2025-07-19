import tkinter as tk
from interface.styling import *

class RealTimeStatsPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent,  **kwargs)
        kwargs.setdefault("bg", BG_COLOR)
        self.vars = {
            "Total Trades": tk.StringVar(value="0"),
            # You can add more stats dynamically
        }

        self.label_frames = {}

        for label, var in self.vars.items():
            self._create_label_row(label, var)

    def _create_label_row(self, label, var):
        frame = tk.Frame(self, bg=BG_COLOR)
        frame.pack(anchor="w", pady=5, padx=10)
        self.label_frames[label] = frame

        tk.Label(frame, text=f"{label}:", font=GLOBAL_FONT, fg=FG_COLOR_WHITE, bg=BG_COLOR).pack(side=tk.LEFT)
        tk.Label(frame, textvariable=var, font=GLOBAL_FONT, fg=FG_COLOR_STEEL_BLUE, bg=BG_COLOR).pack(side=tk.LEFT, padx=5)

    def set_stat(self, label, value):
        """Update or add a specific stat."""
        if label in self.vars:
            self.vars[label].set(value)
        else:
            self.vars[label] = tk.StringVar(value=value)
            self._create_label_row(label, self.vars[label])

    def bind_trade_counter(self, trade_counter):
        self._trade_counter = trade_counter
        self._update_trade_count()

    def _update_trade_count(self):
        if hasattr(self, "_trade_counter"):
            count = self._trade_counter.get()
            self.set_stat("Total Trades", str(count))
            self.after(1000, self._update_trade_count)
