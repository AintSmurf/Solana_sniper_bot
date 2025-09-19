import os
import pandas as pd
from helpers.logging_manager import LoggingHandler
from datetime import datetime

# set up logger
logger = LoggingHandler.get_logger()


class ExcelUtility:
    def __init__(self):
        #1st layer
        self.base_dir = os.path.abspath("results")

        #2nd layer      
        self.TOKENS_DIR = os.path.join(self.base_dir, "tokens")
        self.BACKTEST_DIR = os.path.join(self.base_dir, "backtest")
        self.NOTIFICATIONS = os.path.join(self.base_dir, "notifications")

        #3rd layer
        self.OPEN_POISTIONS = os.path.join(self.TOKENS_DIR, "open_poistions")
        self.CLOSED_POISTIONS = os.path.join(self.TOKENS_DIR, "closed_poistions")
        self.FAILED_TOKENS = os.path.join(self.TOKENS_DIR, "failed_tokens")


        self.create_folders()

    def create_folders(self):
        os.makedirs(self.TOKENS_DIR, exist_ok=True)
        os.makedirs(self.BACKTEST_DIR, exist_ok=True)
        os.makedirs(self.OPEN_POISTIONS, exist_ok=True)
        os.makedirs(self.CLOSED_POISTIONS, exist_ok=True)
        os.makedirs(self.FAILED_TOKENS, exist_ok=True)
        os.makedirs(self.NOTIFICATIONS, exist_ok=True)
        logger.info("✅ Successfully created folders ..")

    def save_to_csv(self, directory, filename, data):
        filepath = os.path.join(directory, filename)
        df = pd.DataFrame(data)

        if os.path.exists(filepath):
            existing_df = pd.read_csv(filepath)
            updated_df = pd.concat([existing_df, df], ignore_index=True)
        else:
            updated_df = df

        updated_df.to_csv(filepath, index=False)
        logger.debug(f"✅ Data saved to {filepath}")
    
    def remove_row_by_token(self, filepath: str, token_mint: str):
        try:
            df = pd.read_csv(filepath)
            initial_len = len(df)
            df = df[df["Token_bought"] != token_mint]
            df.to_csv(filepath, index=False)

            if len(df) < initial_len:
                logger.debug(f"🧼 Removed token {token_mint} from {filepath}")
            else:
                logger.warning(f"⚠️ Token {token_mint} not found in {filepath}")
        except Exception as e:
            logger.error(f"❌ Failed to remove token from {filepath}: {e}")
    
    def load_closed_positions(self, simulated):
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        filename = f"simulated_closed_positions_{date_str}.csv" if simulated else f"closed_positions_{date_str}.csv"
        filepath = os.path.join(self.CLOSED_POISTIONS, filename)

        if not os.path.exists(filepath):
            logger.warning(f"⚠️ {filename} does not exist yet.")
            return pd.DataFrame() 
        try:
            return pd.read_csv(filepath)
        except Exception as e:
            logger.error(f"❌ Failed to load {filename}: {e}")
            return pd.DataFrame()

