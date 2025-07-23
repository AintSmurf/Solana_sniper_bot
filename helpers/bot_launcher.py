import threading
import asyncio
from discord_bot.bot import Discord_Bot
from helpers.open_positions import OpenPositionTracker
from helpers.rate_limiter import RateLimiter
from connectors.helius_connector import HeliusConnector
from helpers.logging_manager import LoggingHandler

logger = LoggingHandler.get_logger()
discord_bot = Discord_Bot()

def start_discord_bot():
    asyncio.run(discord_bot.run())

def start_bot(trade_counter, settings):
    stop_ws = threading.Event()
    stop_fetcher = threading.Event()
    stop_tracker = threading.Event()
    stop_retry = threading.Event()

    helius_rl = settings["RATE_LIMITS"]["helius"]
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
        rate_limiter=helius_limiter
    )

    threading.Thread(target=helius_connector.start_ws, daemon=True).start()
    threading.Thread(target=helius_connector.run_transaction_fetcher, daemon=True).start()
    threading.Thread(target=tracker.track_positions, args=(stop_tracker,), daemon=True).start()
    threading.Thread(target=tracker.retry_failed_sells, args=(stop_retry,), daemon=True).start()
    threading.Thread(target=start_discord_bot, daemon=True).start()

    logger.info("🚀 All threads started")
    return stop_ws, stop_fetcher, stop_tracker, stop_retry, tracker
