from utilities.excel_utility import ExcelUtility
from utilities.requests_utility import RequestsUtility
from helpers.logging_manager import LoggingHandler
from config.network import HELIUS_URL,HELIUS_ENHANCED
from utilities.rug_check_utility import RugCheckUtility
from helpers.trade_counter import TradeCounter
from helpers.rate_limiter import RateLimiter
from config.third_parties import JUPITER_STATION


class BotContext:
    def __init__(self, settings, api_keys: dict, settings_manager,first_run):
        self.services = {}
        self.settings_manager = settings_manager
        self.settings = settings
        self.api_keys = api_keys
        self.first_run = first_run

        # Rate limiters
        rl_cfg = settings["RATE_LIMITS"]
        self.rate_limiters = {
            "helius": RateLimiter(
                min_interval=rl_cfg["helius"]["min_interval"],
                jitter_range=tuple(rl_cfg["helius"]["jitter_range"]),
                max_requests_per_minute=rl_cfg["helius"]["max_requests_per_minute"],
                name=rl_cfg["helius"]["name"],
            ),
            "jupiter": RateLimiter(
                min_interval=rl_cfg["jupiter"]["min_interval"],
                jitter_range=tuple(rl_cfg["jupiter"]["jitter_range"]),
                max_requests_per_minute=rl_cfg["jupiter"]["max_requests_per_minute"],
                name=rl_cfg["jupiter"]["name"],
            ),
        }

        # classes
        self.excel_utility = ExcelUtility()
        self.rug_check = RugCheckUtility()
        self.trade_counter = TradeCounter(settings["MAXIMUM_TRADES"])


        
        #requests instances
        self.helius_requests = RequestsUtility(HELIUS_URL[self.settings["NETWORK"]])
        self.helius_enhanced = RequestsUtility(HELIUS_ENHANCED[self.settings["NETWORK"]])
        self.jupiter_requests = RequestsUtility(JUPITER_STATION["BASE_URL"])

        #logs
        self.logger = LoggingHandler.get_logger()
        self.special_logger = LoggingHandler.get_special_debug_logger()
        self.tracker_logger = LoggingHandler.get_named_logger("tracker")

    def register(self, name: str, service: object):
        self.services[name] = service

    def get(self, name: str):
        return self.services.get(name)