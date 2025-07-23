import asyncio
from helpers.logging_manager import LoggingHandler
from helpers.trade_counter import TradeCounter
from helpers.bot_runner import prepare_settings, handle_cli_mode, handle_ui_mode
from helpers.bot_launcher import start_bot
import argparse
from discord_bot.bot import Discord_Bot


# set up logger
logger = LoggingHandler.get_logger()
discord_bot = Discord_Bot()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--s', '--server', dest='server', action='store_true', help='Run in server mode (no CLI loop)')
    args = parser.parse_args()
    settings = prepare_settings(headless=args.server)
    
    if args.server:
        trade_counter = TradeCounter(settings["MAXIMUM_TRADES"])
        stop_ws, stop_fetcher, stop_tracker, stop_retry, tracker = start_bot(trade_counter, settings)        
        handle_cli_mode(trade_counter, tracker, stop_ws, stop_fetcher, stop_tracker, stop_retry)
        stop_ws.set()
        stop_fetcher.set()
        stop_tracker.set()
        stop_retry.set()
        try:
            asyncio.run(discord_bot.shutdown())
        except Exception as e:
            logger.warning(f"⚠️ Discord bot shutdown failed: {e}")

    elif settings["UI_MODE"]:
        handle_ui_mode()
    else:
        # CLI mode — start everything directly
        trade_counter = TradeCounter(settings["MAXIMUM_TRADES"])
        stop_ws, stop_fetcher, stop_tracker, stop_retry, tracker = start_bot(trade_counter, settings)

        handle_cli_mode(trade_counter, tracker, stop_ws, stop_fetcher, stop_tracker, stop_retry)

        stop_ws.set()
        stop_fetcher.set()
        stop_tracker.set()
        stop_retry.set()
        try:
            asyncio.run(discord_bot.shutdown())
        except Exception as e:
            logger.warning(f"⚠️ Discord bot shutdown failed: {e}")

    logger.info("🛑 Bot fully shutdown.")
    exit(0)



if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"❌ BOT_SETTINGS validation failed: {e}")
        exit(1)
