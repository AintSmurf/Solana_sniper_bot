import time
import asyncio
from config.settings import load_settings, prompt_bot_settings, prompt_ui_mode
from helpers.framework_manager import validate_bot_settings
from helpers.logging_manager import LoggingHandler
from interface.settings_window import SettingsConfigUI
from interface.sniper_bot_ui import SniperBotUI
from discord_bot.bot import Discord_Bot

logger = LoggingHandler.get_logger()
discord_bot = Discord_Bot()

def prepare_settings(headless=False):
    settings = load_settings()
    if headless:
        return settings

    prompt_ui_mode(settings)
    settings = load_settings()

    if not settings["UI_MODE"]:
        prompt_bot_settings(settings)
        settings = load_settings()

    validate_bot_settings(settings)
    return settings

def handle_ui_mode():
    config_window = SettingsConfigUI()
    config_window.mainloop()

    # Reload if user changed config in UI
    app = SniperBotUI()
    app.mainloop()
    return True

def handle_cli_mode(trade_counter, tracker, stop_ws, stop_fetcher, stop_tracker, stop_retry):
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
