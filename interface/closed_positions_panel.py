import tkinter as tk
from tkinter import ttk
from interface.styling import *

class ClosedPositionsPanel(tk.Frame):
    def __init__(self, parent, ctx, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.ctx = ctx
        self.settings = ctx.settings
        self.excel_utility = ctx.excel_utility
        
        kwargs.setdefault("bg", BG_COLOR)
        kwargs.setdefault("bg", BG_COLOR)

        style = ttk.Style()
        style.theme_use("default")

        style.configure("Custom.Treeview",
                        background=BG_COLOR,
                        fieldbackground=BG_COLOR,
                        foreground=FG_COLOR_WHITE,
                        rowheight=24,
                        font=GLOBAL_FONT)

        style.configure("Custom.Treeview.Heading",
                        background=BG_COLOR_2,
                        foreground=FG_COLOR_WHITE,
                        font=("Calibri", 11, "bold"))

        style.map("Custom.Treeview.Heading",
                background=[("active", BG_COLOR_2), ("pressed", BG_COLOR_2)],
                foreground=[("active", FG_COLOR_WHITE), ("pressed", FG_COLOR_WHITE)])

        self.columns = ["Buy_Timestamp","Sell_Timestamp", "Token Address","Entry_USD", "Exit_USD", "PnL (%)", "Trigger"]
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", style="Custom.Treeview")

        for col in self.columns:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_by(c, False))
            self.tree.column(col, anchor="center", width=120)

        self.tree.pack(fill=tk.BOTH, expand=True)

        self._sort_descending = {}  # track sort order per column

    def update_table(self, df):
        self.tree.delete(*self.tree.get_children())
        for _, row in df.iterrows():
            pnl_value = row["PnL (%)"]
            tag = "profit" if pnl_value >= 0 else "loss"

            self.tree.insert("", "end", values=(
                row["Buy_Timestamp"],
                row["Sell_Timestamp"],
                row["Token Mint"],
                f"{row['Entry_USD']:.6f}",
                f"{row['Exit_USD']:.6f}",
                f"{pnl_value:.2f}%",
                row["Trigger"]
            ), tags=(tag,))
            
        self.tree.tag_configure("profit", foreground="lightgreen")
        self.tree.tag_configure("loss", foreground="red")

    def sort_by(self, col, descending):
        """Sort tree contents when a column header is clicked."""
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]

        # try to parse numbers (esp for PnL, Entry, Exit)
        def convert(val):
            try:
                return float(val.replace("%", ""))  # handle % column
            except:
                return val

        data = [(convert(v), k) for v, k in data]

        # sort
        data.sort(reverse=descending)

        # rearrange items in sorted positions
        for idx, (val, k) in enumerate(data):
            self.tree.move(k, '', idx)

        # flip sort order for next click
        self._sort_descending[col] = not descending
        self.tree.heading(col, command=lambda c=col: self.sort_by(c, self._sort_descending[col]))

    def refresh(self):
        df = self.excel_utility.load_closed_positions(self.settings["SIM_MODE"])
        self.update_table(df)
