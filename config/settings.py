import json
import os
from helpers.logging_manager import LoggingHandler

logger = LoggingHandler.get_logger()

DEFAULT_SETTINGS = {
    #bot settings
    "UI_MODE": False,
    "MIN_TOKEN_LIQUIDITY": 10000,
    "MAX_TOKEN_AGE_SECONDS": 30,
    "TRADE_AMOUNT": 10,
    "MAXIMUM_TRADES": 20,
    "SIM_MODE": True,

    # Trading logic
    "TP": 4.0,                              # Take profit = 4x
    "SL": 0.25,                             # Emergency SL: trigger if price drops 25% or more
    "TRAILING_STOP": 0.2,                   # TSL: 20% drop from peak
    "MIN_TSL_TRIGGER_MULTIPLIER": 1.5,      # Enable TSL only after token pumps to 1.5x

    #api settings
    "RATE_LIMITS": {
        "helius": {
            "min_interval": 0.02,
            "jitter_range": [0.005, 0.01]
        },
        "jupiter": {
            "min_interval": 1.1,
            "jitter_range": [0.05, 0.15],
            "max_requests_per_minute": 60
        }
    }
}


SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "bot_settings.json")

def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                loaded = json.load(f)
                merged = merge_with_defaults(loaded, DEFAULT_SETTINGS)
                for api in ["helius", "jupiter"]:
                    jitter = merged["RATE_LIMITS"][api].get("jitter_range")
                    if jitter and len(jitter) == 2:
                        merged["RATE_LIMITS"][api]["jitter_range"] = tuple(jitter)

                return merged
        except Exception as e:
            logger.warning(f"⚠️ Failed to load settings file: {e}")

    # File doesn't exist or failed to load — create with defaults
    defaults = DEFAULT_SETTINGS.copy()
    save_settings(defaults)
    logger.info("📁 Created default bot_settings.json")
    return defaults

def save_settings(settings: dict):
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=4)

def merge_with_defaults(user_settings, default_settings):
    result = default_settings.copy()
    for key, val in user_settings.items():
        if isinstance(val, dict) and key in result:
            result[key] = merge_with_defaults(val, result[key])
        else:
            result[key] = val
    return result

def prompt_bot_settings(settings):
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
            elif isinstance(val, list) and len(val) == 2:
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
                    print(f"  🔹 {sub_key} Rate Limit Settings:")
                    for rate_key, rate_val in settings[key][sub_key].items():
                        full_key = f"{sub_key}.{rate_key}"
                        settings[key][sub_key][rate_key] = prompt_value(full_key, rate_val)
                else:
                    full_key = f"{key}.{sub_key}"
                    settings[key][sub_key] = prompt_value(full_key, settings[key][sub_key])
        else:
            settings[key] = prompt_value(key, settings[key])

    save_settings(settings)
    logger.info("✅ Settings saved to bot_settings.json\n")

def get_bot_settings():
    settings = load_settings()
    return settings

def prompt_ui_mode(settings):
    default_ui = settings.get("UI_MODE", False)
    user_input = input(f"Would you like to launch the bot with a graphical interface? (yes/no) [{default_ui}]: ").strip().lower()

    if user_input in ("yes", "y", "true", "1"):
        settings["UI_MODE"] = True
    elif user_input in ("no", "n", "false", "0"):
        settings["UI_MODE"] = False
    # Else keep default

    save_settings(settings)
    return settings["UI_MODE"]

