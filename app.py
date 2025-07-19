import asyncio
from discord_bot.bot import Discord_Bot
from connectors.helius_connector import HeliusConnector
from helpers.logging_manager import LoggingHandler
import threading
import time
from helpers.open_positions import OpenPositionTracker
from helpers.rate_limiter import RateLimiter
from config.bot_settings import BOT_SETTINGS
from helpers.framework_manager import validate_bot_settings
from helpers.trade_counter import TradeCounter
from interface.main_window import SniperBotUI

# set up logger
logger = LoggingHandler.get_logger()
discord_bot = Discord_Bot()


def start_discord_bot():
    asyncio.run(discord_bot.run())

def start_bot(trade_counter):
    stop_ws = threading.Event()
    stop_fetcher = threading.Event()
    stop_tracker = threading.Event()
    stop_retry = threading.Event()

    # Setup shared rate limiter
    helius_rl = BOT_SETTINGS["RATE_LIMITS"]["helius"]
    helius_limiter = RateLimiter(
        min_interval=helius_rl["min_interval"],
        jitter_range=helius_rl["jitter_range"]
    )

    helius_connector = HeliusConnector(
        rate_limiter=helius_limiter,
        trade_counter=trade_counter,
        stop_ws=stop_ws,
        stop_fetcher=stop_fetcher
    )

    tracker = OpenPositionTracker(
        tp=BOT_SETTINGS["TP"],
        sl=BOT_SETTINGS["SL"],
        rate_limiter=helius_limiter
    )

    threading.Thread(target=helius_connector.start_ws, daemon=True).start()
    threading.Thread(target=helius_connector.run_transaction_fetcher, daemon=True).start()
    threading.Thread(target=tracker.track_positions, args=(stop_tracker,), daemon=True).start()
    threading.Thread(target=tracker.retry_failed_sells, args=(stop_retry,), daemon=True).start()
    threading.Thread(target=start_discord_bot, daemon=True).start()

    logger.info("🚀 All threads started")
    return stop_ws, stop_fetcher, stop_tracker, stop_retry, tracker

def main():
    validate_bot_settings()
    trade_counter = TradeCounter(BOT_SETTINGS["MAXIMUM_TRADES"])
    stop_ws, stop_fetcher, stop_tracker, stop_retry, tracker = start_bot(trade_counter)

    if BOT_SETTINGS["UI_MODE"]:
        # 👀 GUI mode — launch interface and wait for user to close it
        app = SniperBotUI(trade_counter)
        app.mainloop()

        # After UI is closed
        stop_ws.set()
        stop_fetcher.set()
        stop_tracker.set()
        stop_retry.set()
        try:
            asyncio.run(discord_bot.shutdown())
        except Exception as e:
            logger.warning(f"⚠️ Discord bot shutdown failed: {e}")

    else:
        # ⌨️ Terminal mode — loop until shutdown
        while True:
            time.sleep(5)
            if trade_counter.reached_limit():
                if not stop_ws.is_set():
                    logger.warning("🚫 MAX TRADES hit — stopping trade threads.")
                    stop_ws.set()
                    stop_fetcher.set()
                if not tracker.has_open_positions() and not tracker.has_failed_sells():
                    logger.info("✅ Trades done — shutting everything down.")
                    stop_tracker.set()
                    stop_retry.set()
                    try:
                        asyncio.run(discord_bot.shutdown())
                    except Exception as e:
                        logger.warning(f"⚠️ Discord bot shutdown failed: {e}")
                    break

    logger.info("🛑 Bot fully shutdown.")
    exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ BOT_SETTINGS validation failed: {e}")
        exit(1)
