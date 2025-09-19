import time
from collections import deque
from helpers.bot_context import BotContext

class VolumeTracker:
    def __init__(self, ctx: BotContext):
        self.ctx = ctx
        self.excel_utility = self.ctx.excel_utility
        self.volume_by_token = {}
        self.token_launch_info = {}

    def record_trade(self, token_mint: str, volume: dict, signature: str):
        """Record both buy and sell trades from a volume dict, tied to a transaction signature."""
        now = time.time()
        if token_mint not in self.volume_by_token:
            self.volume_by_token[token_mint] = deque(maxlen=10000)

        # Record buys
        if volume.get("buy_usd", 0) > 0:
            self.volume_by_token[token_mint].append((now, volume["buy_usd"], "buy", signature))

        # Record sells
        if volume.get("sell_usd", 0) > 0:
            self.volume_by_token[token_mint].append((now, volume["sell_usd"], "sell", signature))

    def snapshot_launch(self, token_mint: str, timestamp: float, first_trade_usd: float, signature: str):
        """Create a snapshot when token is first seen (with first trade volume + signature)."""
        self.token_launch_info[token_mint] = {
            "launch_time": timestamp,
            "launch_volume": first_trade_usd,
            "first_signature": signature
        }

        if self.excel_utility:
            self.excel_utility.save_to_csv(
                self.excel_utility.BACKTEST_DIR,
                "token_volume.csv",
                {
                    "Token Mint": [token_mint],
                    "Launch Timestamp": [time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))],
                    "Launch Volume": [first_trade_usd],
                    "First Signature": [signature],
                },
            )

    def stats(self, token_mint: str, window=300):
        now = time.time()
        trades = self.volume_by_token.get(token_mint, [])
        recent = [(ts, usd, ttype) for ts, usd, ttype in trades if now - ts <= window]

        total_buy = sum(usd for _, usd, ttype in recent if ttype == "buy")
        total_sell = sum(usd for _, usd, ttype in recent if ttype == "sell")
        total_usd = total_buy + total_sell

        launch = self.token_launch_info.get(token_mint, {})
        launch_time = launch.get("launch_time")
        launch_volume = launch.get("launch_volume", 0.0)

        return {
            "count": len(recent),
            "buy_usd": round(total_buy, 2),
            "sell_usd": round(total_sell, 2),
            "total_usd": round(total_usd, 2),
            "buy_count": sum(1 for _, _, ttype in recent if ttype == "buy"),
            "sell_count": sum(1 for _, _, ttype in recent if ttype == "sell"),
            "buy_ratio": round((total_buy / total_usd * 100) if total_usd > 0 else 0, 2),
            "net_flow": round(total_buy - total_sell, 2),
            "launch_time": launch_time,
            "volume_since_launch": round(sum(usd for _, usd, _ in trades) - launch_volume, 2),
        }
