import json
import os
import copy
from helpers.logging_manager import LoggingHandler

logger = LoggingHandler.get_logger()

DEFAULT_SETTINGS = {
    
    #Modes
    "NETWORK":"mainnet",
    "SIM_MODE": True,
    "UI_MODE": False,


    # bot settings
    "MIN_TOKEN_LIQUIDITY": 10000,
    "MAX_TOKEN_AGE_SECONDS": 30,
    "TRADE_AMOUNT": 10,
    "MAXIMUM_TRADES": 20,
    "TIMEOUT_SECONDS": 45,
    "TIMEOUT_PROFIT_THRESHOLD": 1.03,

    # Trading logic thresholds
    "SLPG":3.0,
    "TP": 4.0,                              
    "SL": 0.25,                             
    "TRAILING_STOP": 0.2,                   
    "MIN_TSL_TRIGGER_MULTIPLIER": 1.5,      

    # ✅ Exit rule toggles
    "EXIT_RULES": {
        "USE_TP": False,
        "USE_TSL": False,
        "USE_SL": False,
        "USE_TIMEOUT": False
    },

    # ✅ Notification channels
    "NOTIFY": {
        "DISCORD": False,
        "TELEGRAM": False,
        "SLACK": False,
    },

    # API rate limits
    "RATE_LIMITS": {
        "helius": {
            "min_interval": 0.02,
            "jitter_range": [
                0.005,
                0.01
            ],
            "max_requests_per_minute": None,
            "name":"Helius_limits"
        },
        "jupiter": {
            "min_interval": 1.0,
            "jitter_range": [
                0.05,
                0.15
            ],
            "max_requests_per_minute": 60,
            "name":"Jupiter_limits"
        }
    }
}

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "bot_settings.json")

class Settings:

    def load_settings(self):
        """Load settings file, merging with defaults and enforcing types."""
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r") as f:
                    loaded = json.load(f)
                    merged = self.merge_with_defaults(loaded, DEFAULT_SETTINGS)

                    # normalize jitter ranges as tuples
                    for api in ["helius", "jupiter"]:
                        jitter = merged["RATE_LIMITS"][api].get("jitter_range")
                        if jitter and len(jitter) == 2:
                            merged["RATE_LIMITS"][api]["jitter_range"] = tuple(jitter)

                    return merged
            except Exception as e:
                logger.warning(f"⚠️ Failed to load settings file: {e}")

        # fallback: write fresh defaults
        defaults = copy.deepcopy(DEFAULT_SETTINGS)
        self.save_settings(defaults)
        logger.info("Created default bot_settings.json")
        return defaults

    def save_settings(self,settings: dict):
        """Write settings to JSON (convert tuples to lists for JSON compatibility)."""
        serializable = copy.deepcopy(settings)

        for api in ["helius", "jupiter"]:
            if "jitter_range" in serializable["RATE_LIMITS"][api]:
                jr = serializable["RATE_LIMITS"][api]["jitter_range"]
                serializable["RATE_LIMITS"][api]["jitter_range"] = list(jr)

        with open(SETTINGS_PATH, "w") as f:
            json.dump(serializable, f, indent=4)

    def merge_with_defaults(self,user_settings, default_settings):
        """Recursive merge of user and default settings."""
        result = copy.deepcopy(default_settings)
        for key, val in user_settings.items():
            if isinstance(val, dict) and key in result:
                result[key] = self.merge_with_defaults(val, result[key])
            else:
                result[key] = val
        return result

    def prompt_bot_settings(self,settings):
        print("\n🔧 Configure Sniper Bot Settings (press Enter to keep default):\n")

        def prompt_value(key, val):
            user_input = input(f"{key} [{val}]: ").strip()
            if not user_input:
                return val
            try:
                if isinstance(val, bool):
                    return user_input.lower() in ("true", "1", "yes", "on")
                elif isinstance(val, int):
                    return int(user_input)
                elif isinstance(val, float):
                    return float(user_input)
                elif isinstance(val, (list, tuple)) and len(val) == 2:
                    parts = user_input.split(",")
                    if len(parts) == 2:
                        return [float(parts[0]), float(parts[1])]
                    else:
                        raise ValueError("Invalid list format")
                else:
                    return user_input
            except Exception:
                logger.error(f"❌ Invalid input for {key}, keeping default.")
                return val

        for key in settings:
            if key == "UI_MODE":
                continue
            if isinstance(settings[key], dict):
                print(f"\n📦 {key} Settings:")
                for sub_key in settings[key]:
                    if isinstance(settings[key][sub_key], dict):
                        print(f"  🔹 {sub_key} Settings:")
                        for rate_key, rate_val in settings[key][sub_key].items():
                            full_key = f"{sub_key}.{rate_key}"
                            settings[key][sub_key][rate_key] = prompt_value(full_key, rate_val)
                    else:
                        full_key = f"{key}.{sub_key}"
                        settings[key][sub_key] = prompt_value(full_key, settings[key][sub_key])
            else:
                settings[key] = prompt_value(key, settings[key])

        self.save_settings(settings)
        logger.info("✅ Settings saved to bot_settings.json")

    def get_bot_settings(self):
        return self.load_settings()

    def prompt_ui_mode(self,settings):
        default_ui = settings.get("UI_MODE", False)
        user_input = input(f"Would you like to launch the bot with a graphical interface? (y/n) [{default_ui}]: ").strip().lower()

        if user_input in ("yes", "y", "true", "1"):
            settings["UI_MODE"] = True
        elif user_input in ("no", "n", "false", "0"):
            settings["UI_MODE"] = False
        else:
            logger.warning(f"⚠️ Invalid input for UI_MODE, keeping [{default_ui}]")
            settings["UI_MODE"] = default_ui

        self.save_settings(settings)
        return settings["UI_MODE"]

    def validate_bot_settings(self, settings):
        # Ensure all top-level keys exist
        for key in DEFAULT_SETTINGS:
            if key not in settings:
                raise ValueError(f"Missing setting: {key}")
        # Network
        if not isinstance(settings["NETWORK"], str):
            raise TypeError("NETWORK must be a string")
        if settings["NETWORK"] not in ("mainnet", "devnet"):
            raise ValueError(f"Invalid NETWORK: {settings['NETWORK']} (must be 'mainnet', 'devnet', or 'testnet')")


        # Core numbers
        if not isinstance(settings["MIN_TOKEN_LIQUIDITY"], (int, float)):
            raise TypeError("MIN_TOKEN_LIQUIDITY must be a number")

        if not isinstance(settings["MAX_TOKEN_AGE_SECONDS"], int):
            raise TypeError("MAX_TOKEN_AGE_SECONDS must be an integer")

        if not isinstance(settings["TRADE_AMOUNT"], (int, float)):
            raise TypeError("TRADE_AMOUNT must be a number")

        if not isinstance(settings["MAXIMUM_TRADES"], int):
            raise TypeError("MAXIMUM_TRADES must be an integer")

        if not isinstance(settings["SIM_MODE"], bool):
            raise TypeError("SIM_MODE must be a bool")

        if not isinstance(settings["UI_MODE"], bool):
            raise TypeError("UI_MODE must be a bool")

        # Trading thresholds
        for key in ["TP", "SL", "TRAILING_STOP", "MIN_TSL_TRIGGER_MULTIPLIER", "TIMEOUT_PROFIT_THRESHOLD"]:
            if not isinstance(settings[key], (int, float)):
                raise TypeError(f"{key} must be a number (int or float)")

        if not isinstance(settings["TIMEOUT_SECONDS"], int):
            raise TypeError("TIMEOUT_SECONDS must be an integer")

        # Exit rules
        exit_rules = settings.get("EXIT_RULES", {})
        if not isinstance(exit_rules, dict):
            raise TypeError("EXIT_RULES must be a dict")
        for k in DEFAULT_SETTINGS["EXIT_RULES"]:
            if k not in exit_rules:
                raise ValueError(f"Missing EXIT_RULE: {k}")
            if not isinstance(exit_rules[k], bool):
                raise TypeError(f"EXIT_RULES.{k} must be a bool")

        # Notification settings
        notify = settings.get("NOTIFY", {})
        if not isinstance(notify, dict):
            raise TypeError("NOTIFY must be a dict")
        for k in ["DISCORD", "TELEGRAM", "SLACK"]:
            if not isinstance(notify.get(k, False), bool):
                raise TypeError(f"NOTIFY.{k} must be a bool")

        # API rate limits
        rl = settings.get("RATE_LIMITS", {})
        for api in ["helius", "jupiter"]:
            if api not in rl:
                raise ValueError(f"Missing RATE_LIMITS config for: {api}")
            if not isinstance(rl[api].get("min_interval"), (int, float)):
                raise TypeError(f"{api} min_interval must be a number")
            if not isinstance(rl[api].get("max_requests_per_minute"), (int, float, type(None))):
                raise TypeError(f"{api} max_requests_per_minute must be a number or None")

            jitter = rl[api].get("jitter_range")
            if not (
                isinstance(jitter, (list, tuple)) and
                len(jitter) == 2 and
                all(isinstance(j, (int, float)) for j in jitter)
            ):
                raise TypeError(f"{api} jitter_range must be a list/tuple of 2 numbers")


        logger.info("✅ BOT_SETTINGS validation passed")
        return True

    def is_first_run(self) -> bool:
        return not os.path.exists(SETTINGS_PATH)



