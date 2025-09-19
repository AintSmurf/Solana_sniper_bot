import threading
import time
from helpers.open_positions import OpenPositionTracker
from connectors.helius_connector import HeliusConnector
from helpers.logging_manager import LoggingHandler
from notification.manager import NotificationManager
from helpers.bot_context import BotContext
from helpers.solana_manager import SolanaManager
from helpers.volume_tracker import VolumeTracker



logger = LoggingHandler.get_logger()


class BotOrchestrator:
    def __init__(self, ctx: BotContext):
        self.ctx = ctx
        self.settings = self.ctx.settings
        self.trade_counter = self.ctx.trade_counter
        self.trade_counter.reset()
        
        self.volume_tracker = VolumeTracker(ctx=ctx)
        self.ctx.register("volume_tracker",  self.volume_tracker)

        self.solana_manager = SolanaManager(ctx=ctx)
        self.ctx.register("solana_manager", self.solana_manager)

        self.tracker = OpenPositionTracker(ctx=ctx)
        self.ctx.register("open_position_tracker",  self.tracker)

        self.notification_manager = NotificationManager(ctx=ctx)
        self.ctx.register("notification_manager", self.notification_manager)

        # Stop flags
        self.stop_ws = threading.Event()
        self.stop_fetcher = threading.Event()
        self.stop_tracker = threading.Event()
        self.stop_retry = threading.Event()
        
        # Core components
        self.helius_connector = HeliusConnector(
            ctx=ctx,
            stop_ws=self.stop_ws,
            stop_fetcher=self.stop_fetcher,
        )

        self.threads: list[threading.Thread] = []

    def _safe_run(self, target, name, *args):
        def wrapper():
            while not self.stop_ws.is_set():
                try:
                    target(*args)
                except Exception as e:
                    logger.error(f"❌ Thread {name} crashed: {e}", exc_info=True)
                    time.sleep(2)
                else:
                    break 
        t = threading.Thread(target=wrapper, daemon=True, name=name)
        t.start()
        self.threads.append(t)

    def start(self):
        """Start core trading threads + notifier loop thread."""
        self._safe_run(self.helius_connector.start_ws, "WebSocket")
        self._safe_run(self.helius_connector.run_transaction_fetcher, "Fetcher")
        self._safe_run(self.tracker.track_positions, "Tracker", self.stop_tracker)
        self._safe_run(self.tracker.retry_failed_sells, "Retry", self.stop_retry)

        # Start notifications (its own asyncio loop thread)
        self.notification_manager.start()

        logger.info("🚀 Bot started with all components")

    def run_cli_loop(self):
        """Blocking CLI watcher until trades complete."""
        while True:
            time.sleep(5)

            if  self.trade_counter.reached_limit():
                logger.warning("🚫 MAX TRADES hit — stopping trade threads.")
                self.stop_ws.set()
                self.stop_fetcher.set()
                if not self.tracker.has_open_positions() and not self.tracker.has_failed_sells():
                    logger.info("✅ Trades done — shutting everything down.")
                    self.shutdown()
                    break

    def shutdown(self):
        """Graceful shutdown of trading threads and notifiers."""
        # 1. Stop all loops
        for stop in (self.stop_ws, self.stop_fetcher, self.stop_tracker, self.stop_retry):
            stop.set()

        # 2. Close WS
        try:
            if hasattr(self, "helius_connector"):
                self.helius_connector.close()
        except Exception as e:
            logger.warning(f"⚠️ Failed to close WebSocket: {e}")

        # 3. Stop notifier
        try:
            self.notification_manager.shutdown()
        except Exception as e:
            logger.warning(f"⚠️ Notifier shutdown failed: {e}")

        # 4. Join worker threads
        for t in self.threads:
            if t.is_alive():
                t.join(timeout=2)

        logger.info("🛑 Bot fully shutdown.")
    
