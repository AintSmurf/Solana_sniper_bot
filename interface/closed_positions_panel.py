import tkinter as tk
from tkinter import ttk
import pandas as pd
from interface.styling import *

class ClosedPositionsPanel(tk.Frame):
    def __init__(self, parent, excel_utility=None, **kwargs):
        super().__init__(parent, **kwargs)
        kwargs.setdefault("bg", BG_COLOR)
        self.excel_utility = excel_utility

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=BG_COLOR,
                        foreground=FG_COLOR_STEEL_BLUE,
                        fieldbackground=BG_COLOR,
                        font=GLOBAL_FONT)
        style.configure("Treeview.Heading",
                        background=BG_COLOR_2,
                        foreground=FG_COLOR_WHITE,
                        font=("Calibri", 11, "bold"))
        style.map("Treeview",
                  background=[("selected", BTN_COLOR)],
                  foreground=[("selected", FG_COLOR_WHITE)])

        columns = ["Timestamp", "Token Mint", "Entry_USD", "Exit_USD", "PnL (%)", "Trigger"]
        self.tree = ttk.Treeview(self, columns=columns, show="headings", style="Treeview")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center", width=100)

        self.tree.pack(fill=tk.BOTH, expand=True)

        # Optional refresh button
        if self.excel_utility:
            refresh_btn = tk.Button(
                self,
                text="🔄 Refresh",
                command=self.refresh,
                bg=BTN_COLOR,
                fg=FG_COLOR_WHITE,
                font=GLOBAL_FONT,
                relief=tk.FLAT
            )
            refresh_btn.pack(pady=5)

    def update_table(self, df):
        self.tree.delete(*self.tree.get_children())
        for _, row in df.iterrows():
            self.tree.insert("", "end", values=(
                row["Timestamp"],
                row["Token Mint"],
                round(row["Entry_USD"], 6),
                round(row["Exit_USD"], 6),
                f'{row["PnL (%)"]:.2f}%',
                row["Trigger"]
            ))

    def refresh(self):
        df = self.excel_utility.load_closed_positions()
        self.update_table(df)
