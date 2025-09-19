from helpers.bot_orchestrator import BotOrchestrator
from interface.sniper_bot_ui import SniperBotUI
from helpers.bot_context import BotContext
import argparse
import sys

class BotApp:
    def __init__(self, ctx:BotContext):
        self.ctx = ctx
        self.orchestrator: BotOrchestrator | None = None

    def run(self, args=None):
        parser = argparse.ArgumentParser(description="Start Sniper Bot")
        parser.add_argument("--s", "--server", dest="server", action="store_true",
                            help="Run in server mode (no UI even if UI_MODE=True)")
        parser.add_argument("--ui", dest="ui", action="store_true",
                            help="Launch UI for this run (overrides settings)")
        parser.add_argument("--cli", dest="cli", action="store_true",
                            help="Launch CLI for this run (overrides settings)")
        parser.add_argument("--no-save", dest="no_save", action="store_true",
                            help="Don't persist the chosen UI/CLI mode into settings file")
        parsed = parser.parse_args(args)

        if parsed.ui and parsed.cli:
            self.ctx.logger.error("Specify only one of --ui or --cli")
            sys.exit(2)

        def persist_ui_mode(mode: bool):
            try:
                self.ctx.settings["UI_MODE"] = bool(mode)
                if not parsed.no_save:
                    try:
                        self.ctx.settings_manager.save_settings(self.ctx.settings)
                    except Exception as e:
                        self.ctx.logger.error(f"⚠️ Failed to save settings: {e}")
            except Exception as e:
                self.ctx.logger.error(f"⚠️ Failed to set UI_MODE in memory: {e}")


        first_run = self.ctx.first_run
                
        if parsed.server:
            launch_ui = False
            first_run = False
            if not parsed.no_save:
                persist_ui_mode(False)
        elif parsed.ui:
            persist_ui_mode(True)
            launch_ui = True
        elif parsed.cli:
            persist_ui_mode(False)
            launch_ui = False
        else:
            saved_mode = bool(self.ctx.settings.get("UI_MODE", False))
            launch_ui = saved_mode

            if first_run and sys.stdin.isatty():
                try:
                    choice = input("First run detected — launch with graphical UI? (y/N): ").strip().lower()
                    launch_ui = choice in ("y", "yes", "true", "1")
                    persist_ui_mode(launch_ui)
                except Exception:
                    launch_ui = saved_mode

        if not launch_ui and first_run and sys.stdin.isatty():
            if hasattr(self.ctx, "settings_manager") and getattr(self.ctx.settings_manager, "prompt_bot_settings", None):
                try:
                    self.ctx.settings_manager.prompt_bot_settings(self.ctx.settings)
                    if not parsed.no_save:
                        try:
                            self.ctx.settings_manager.save_settings(self.ctx.settings)
                        except Exception as e:
                            self.ctx.logger.warning(f"⚠️ Failed to save settings after prompting: {e}")
                except Exception as e:
                    self.ctx.logger.error(f"⚠️ Settings prompt failed: {e}")

        if launch_ui:
            self.run_ui()
        else:
            self.orchestrator = BotOrchestrator(self.ctx)
            self.run_cli()

    def run_ui(self):
        app = SniperBotUI(self.ctx)
        app.mainloop()

    def run_cli(self):
        try:
            self.orchestrator.start()
            self.orchestrator.run_cli_loop()
        finally:
            self.orchestrator.shutdown()

