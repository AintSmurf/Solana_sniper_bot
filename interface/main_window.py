import tkinter as tk
from interface.logging_panel import LoggingPanel
from interface.closed_positions_panel import ClosedPositionsPanel
from interface.realtime_stats_panel import RealTimeStatsPanel
from interface.styling import *
from helpers.trade_counter import TradeCounter
from helpers.logging_manager import LoggingHandler
from interface.ui_log_hanlder import UILogHandler
from utilities.excel_utility import ExcelUtility


class SniperBotUI(tk.Tk):
    def __init__(self, trade_counter: TradeCounter):
        super().__init__()
        self.title("Solana Sniper Bot")
        self.configure(bg=BG_COLOR)
        self.geometry("1100x700")
        self.excel_utility = ExcelUtility()

        # 🔝 Top: Live logging (tracking tokens)
        self.top_frame = tk.Frame(self, bg=BG_COLOR)
        self.top_frame.pack(side=tk.TOP, fill=tk.BOTH, padx=10, pady=5)

        self._logging_frame = LoggingPanel(self.top_frame, bg=BG_COLOR)
        self._logging_frame.pack(fill=tk.BOTH, expand=True)
        
        ui_log_handler = UILogHandler(self._logging_frame)

        # Get the tracker logger only
        tracker_logger = LoggingHandler.get_named_logger("tracker")
        tracker_logger.addHandler(ui_log_handler)

        # 🔻 Bottom: Split left/right
        self.bottom_frame = tk.Frame(self, bg=BG_COLOR)
        self.bottom_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left: Closed Positions
        self.left_frame = tk.Frame(self.bottom_frame, bg=BG_COLOR)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.closed_positions = ClosedPositionsPanel(self.left_frame, bg=BG_COLOR, excel_utility=self.excel_utility)
        self.closed_positions.pack(fill=tk.BOTH, expand=True)
        df = self.excel_utility.load_closed_positions(simulated=False)
        self.closed_positions.update_table(df)

        

        # Right: Stats for the day
        self.right_frame = tk.Frame(self.bottom_frame, bg=BG_COLOR)
        self.right_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.stats_panel = RealTimeStatsPanel(self.right_frame, bg=BG_COLOR)
        self.stats_panel.pack(fill=tk.BOTH, expand=True)
        self.stats_panel.bind_trade_counter(trade_counter)
