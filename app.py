import sys
from helpers.logging_manager import LoggingHandler
from helpers.bot_app import BotApp
from config.settings import Settings
from helpers.bot_context import BotContext
from utilities.credentials_utility import CredentialsUtility


logger = LoggingHandler.get_logger()


def main():
    credentials = CredentialsUtility()
    credentials_dictionary = credentials.get_all()
    
    settings_manager = Settings()
    first_run = settings_manager.is_first_run()
    bot_settings = settings_manager.load_settings()
    settings_manager.validate_bot_settings(bot_settings)

    ctx = BotContext(settings=bot_settings,api_keys=credentials_dictionary,settings_manager=settings_manager, first_run=first_run) 
    app = BotApp(ctx)
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("🛑 Ctrl+C received, shutting down gracefully...")
        if app.orchestrator:
            app.orchestrator.shutdown()
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ BOT_SETTINGS validation failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()


