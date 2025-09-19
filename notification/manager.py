# notification/manager.py
import asyncio
import threading
from notification.discord_bot import Discord_Bot
from helpers.bot_context import BotContext

class NotificationManager:
    def __init__(self, ctx:BotContext):
        self.ctx = ctx
        self.logger = self.ctx.logger
        self.notifiers = []
        self.loop = None
        self.thread = None

        cfg = ctx.settings["NOTIFY"]
        if cfg.get("DISCORD", False):
            self.notifiers.append(Discord_Bot(ctx.api_keys["discord"], self.logger))
            self.logger.info("💬 Discord notifications enabled")

    def start(self):
        if self.thread:
            return

        def runner():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            for n in self.notifiers:
                self.loop.create_task(n.run())
            self.loop.run_forever()

        self.thread = threading.Thread(target=runner, daemon=True)
        self.thread.start()
        self.logger.info("💬 Notification manager started")

    def notify_text(self, message: str, channel_hint: str = "solana_tokens"):
        """Public API — send a message to all notifiers."""
        if not self.loop:
            self.logger.warning("⚠️ Notification loop not running")
            return

        for n in self.notifiers:
            if hasattr(n, "send_message"):
                fut = asyncio.run_coroutine_threadsafe(
                    n.send_message(channel_hint, message), self.loop
                )
                try:
                    fut.result(timeout=5)
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to send message: {e}")

    def shutdown(self):
        if not self.loop:
            return
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()
