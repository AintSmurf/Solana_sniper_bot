import pandas as pd
from utilities.excel_utility import ExcelUtility
from helpers.logging_manager import LoggingHandler
import time
import os
from datetime import datetime
from helpers.solana_manager import SolanaHandler
from helpers.rate_limiter import RateLimiter
import threading
from config.settings import load_settings

logger = LoggingHandler.get_logger()
tracker_logger = LoggingHandler.get_named_logger("tracker")



class OpenPositionTracker:
    def __init__(self,rate_limiter: RateLimiter):
        BOT_SETTINGS = load_settings()
        self.tp = BOT_SETTINGS["TP"]
        self.sl = BOT_SETTINGS["TRAILING_STOP"]
        self.emergency_sl = BOT_SETTINGS["SL"]
        self.min_tsl_trigger = BOT_SETTINGS["MIN_TSL_TRIGGER_MULTIPLIER"]
        self.excel_utility = ExcelUtility()
        self.solana_manager = SolanaHandler(rate_limiter)
        self.running = True
        self.base_token = "So11111111111111111111111111111111111111112"
        self.failed_sells = {}
        self.max_retries = 3
        self.tokens_to_remove = set()
        self.tokens_lock = threading.Lock()
        
        #check bot mode
        self.file_path = os.path.join(self.excel_utility.BOUGHT_TOKENS, "open_positions.csv")
        if BOT_SETTINGS["SIM_MODE"]:
            self.file_path = os.path.join(self.excel_utility.BOUGHT_TOKENS, "simulated_tokens.csv")

    def track_positions(self, stop_event):
        logger.info("📚 Starting to track open positions from Excel...")

        self.peak_price_dict = {}

        while not stop_event.is_set() or self.has_open_positions():
            if not os.path.exists(self.file_path):
                logger.debug("📭 Waiting for buy file to be created...")
                time.sleep(1)
                continue

            try:
                df = pd.read_csv(self.file_path)
                if df.empty:
                    logger.debug("📭 open_positions.csv is empty.")
                    time.sleep(5)
                    continue

                required_columns = {"Token_bought", "Token_sold", "Quote_Price", "type", "Real_Entry_Price", "Timestamp"}
                if not required_columns.issubset(df.columns):
                    logger.info("📄 File exists but missing expected columns — waiting...")
                    time.sleep(1)
                    continue

                df = df[df["type"].isin(["BUY", "SIMULATED_BUY"])]
                token_mints = df["Token_bought"].dropna().tolist()
                mints = list(set(token_mints + [self.base_token]))

                if len(mints) == 2:
                    try:
                        token_price = self.solana_manager.get_token_price(token_mints[0])
                        sol_price = self.solana_manager.get_token_price(self.base_token)
                        price_data = {
                            token_mints[0]: {"price": token_price},
                            self.base_token: {"price": sol_price}
                        }
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to fetch single token prices: {e}")
                        continue
                else:
                    price_data = self.solana_manager.get_token_prices(mints)["data"]

                for idx, row in df.iterrows():
                    token_mint = row["Token_bought"]
                    input_mint = row["Token_sold"]

                    if token_mint not in price_data or input_mint not in price_data or self.base_token not in price_data:
                        logger.warning(f"⚠️ Missing price data for {token_mint} or SOL.")
                        continue

                    if "Entry_USD" in row and not pd.isna(row["Entry_USD"]):
                        buy_price_usd = float(row["Entry_USD"])
                    else:
                        sol_price_usd = float(price_data[self.base_token]["price"])
                        buy_price_sol = float(row["Real_Entry_Price"] if not pd.isna(row["Real_Entry_Price"]) else row["Quote_Price"])
                        buy_price_usd = buy_price_sol * sol_price_usd

                    current_price_usd = float(price_data[token_mint]["price"])
                    change = ((current_price_usd - buy_price_usd) / buy_price_usd) * 100

                    # Update peak price
                    if token_mint not in self.peak_price_dict:
                        self.peak_price_dict[token_mint] = current_price_usd
                    if current_price_usd > self.peak_price_dict[token_mint]:
                        self.peak_price_dict[token_mint] = current_price_usd

                    peak_price = self.peak_price_dict[token_mint]
                    trailing_stop = peak_price * (1 - self.sl)
                    take_profit_price = buy_price_usd * self.tp

                    logger.info(
                        f"🔎 Tracking {token_mint}... Buy: ${buy_price_usd:.10f}, Current: ${current_price_usd:.10f}, Peak: ${peak_price:.10f}, TP: ${take_profit_price:.10f}, TSL: ${trailing_stop:.10f}, Change: {change:.2f}%"
                    )
                    tracker_logger.info(
                        f"🔎 Tracking {token_mint}... Buy: ${buy_price_usd:.10f}, Current: ${current_price_usd:.10f}, Peak: ${peak_price:.10f}, TP: ${take_profit_price:.10f}, TSL: ${trailing_stop:.10f}, Change: {change:.2f}%"
                    )

                    # --- Take Profit ---
                    if current_price_usd >= take_profit_price:
                        logger.info(f"🎯 TAKE PROFIT triggered for {token_mint}!")
                        tracker_logger.info(f"🎯 TAKE PROFIT triggered for {token_mint}!")
                        if row["type"] == "SIMULATED_BUY":
                            self.simulated_sell_and_log(row, current_price_usd, trigger="TP")
                        else:
                            self.sell_and_update(token_mint, input_mint, trigger="TP")
                        continue

                    # --- Trailing Stop Loss ---
                    has_pumped = peak_price >= buy_price_usd * self.min_tsl_trigger
                    if has_pumped and current_price_usd <= trailing_stop:
                        logger.info(f"🪂 TRAILING STOP LOSS triggered for {token_mint}!")
                        tracker_logger.info(f"🪂 TRAILING STOP LOSS triggered for {token_mint}!")
                        if row["type"] == "SIMULATED_BUY":
                            self.simulated_sell_and_log(row, current_price_usd, trigger="TSL")
                        else:
                            self.sell_and_update(token_mint, input_mint, trigger="TSL")
                        continue
                    
                    # --- Emergency Stop Loss (if no pump and dumped hard)
                    emergency_stop = buy_price_usd * (1 - self.emergency_sl)

                    if not has_pumped and current_price_usd <= emergency_stop:
                        logger.warning(f"💀 EMERGENCY SL triggered for {token_mint}!")
                        tracker_logger.warning(f"💀 EMERGENCY SL triggered for {token_mint}!")
                        if row["type"] == "SIMULATED_BUY":
                            self.simulated_sell_and_log(row, current_price_usd, trigger="SL")
                        else:
                            self.sell_and_update(token_mint, input_mint, trigger="SL")
                        continue


                    # --- Timeout (No Pump in 30s) ---
                    try:
                        buy_time = datetime.strptime(row["Timestamp"], "%Y-%m-%d %H:%M:%S")
                        seconds_since_buy = (datetime.now() - buy_time).total_seconds()
                        if seconds_since_buy > 30 and current_price_usd < buy_price_usd * 1.05:
                            logger.info(f"⌛ TIMEOUT triggered for {token_mint} (no pump in 30s) — exiting.")
                            tracker_logger.info(f"⌛ TIMEOUT triggered for {token_mint} — exiting.")
                            if row["type"] == "SIMULATED_BUY":
                                self.simulated_sell_and_log(row, current_price_usd, trigger="TIMEOUT")
                            else:
                                self.sell_and_update(token_mint, input_mint, trigger="TIMEOUT")
                            continue
                    except Exception as e:
                        logger.warning(f"⚠️ Could not parse Timestamp for timeout check: {e}")

                with self.tokens_lock:
                    if self.tokens_to_remove:
                        df = df[~df["Token_bought"].isin(self.tokens_to_remove)]
                        df.to_csv(self.file_path, index=False)
                        logger.info(f"🧼 Removed {len(self.tokens_to_remove)} tokens from open positions.")
                        self.tokens_to_remove.clear()

            except Exception as e:
                logger.error(f"❌ Error in OpenPositionTracker: {e}")

            time.sleep(0.25)

    def sell_and_update(self, token_mint, input_mint, trigger=None):
        try:
            result = self.solana_manager.sell(token_mint, input_mint)

            if not result["success"]:
                logger.warning(f"❌ Sell failed for {token_mint}. Skipping log and update.")
                if token_mint not in self.failed_sells:
                    self.failed_sells[token_mint] = {"input_mint": input_mint, "retries": 1}
                else:
                    self.failed_sells[token_mint]["retries"] += 1
                return

            executed_price_usd = result["executed_price"] 
            signature = result.get("signature", "")

            try:
                current_df = pd.read_csv(self.file_path)
                matched_row = current_df[current_df["Token_bought"] == token_mint]

                if matched_row.empty:
                    logger.warning(f"⚠️ No matching entry price found for {token_mint}")
                    return

                entry_price_sol = float(
                    matched_row.iloc[0]["Real_Entry_Price"]
                    if "Real_Entry_Price" in matched_row.columns and not pd.isna(matched_row.iloc[0]["Real_Entry_Price"])
                    else matched_row.iloc[0]["Quote_Price"]
                )

                # ✅ Convert entry price (SOL) → USD
                price_data = self.solana_manager.get_token_prices([self.base_token])["data"]
                sol_price_usd = float(price_data[self.base_token]["price"])
                entry_price_usd = entry_price_sol * sol_price_usd

            except Exception as e:
                logger.error(f"❌ Failed to read or convert entry price for {token_mint}: {e}")
                return

            pnl = ((executed_price_usd - entry_price_usd) / entry_price_usd) * 100

            data = {
                "Timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                "Token Mint": [token_mint],
                "Entry_USD": [f"{entry_price_usd:.8f}"],
                "Exit_USD": [f"{executed_price_usd:.8f}"],
                "PnL (%)": [f"{pnl:.2f}"],
                "Sell_Signature": [signature],
                "Buy_Signature": [matched_row.iloc[0].get("Signature", "")],
                "Type": ["SOLD"],
                "Trigger": [trigger or "MANUAL"]
            }

            self.excel_utility.save_to_csv(
                self.excel_utility.BOUGHT_TOKENS,
                "closed_positions.csv",
                data,
            )

            with self.tokens_lock:
                self.tokens_to_remove.add(token_mint)

            logger.info(f"✅ Sold {token_mint} | Entry: ${entry_price_usd:.8f} | Exit: ${executed_price_usd:.8f} | PnL: {pnl:.2f}%")

        except Exception as e:
            logger.error(f"❌ Exception in sell_and_update for {token_mint}: {e}")
            if token_mint not in self.failed_sells:
                self.failed_sells[token_mint] = {"input_mint": input_mint, "retries": 1}
            else:
                self.failed_sells[token_mint]["retries"] += 1
  
    def retry_failed_sells(self,stop_event):
        
        while not stop_event.is_set() or self.has_failed_sells():
            if not self.failed_sells:
                time.sleep(5)
                continue

            logger.info(f"🔁 Retrying {len(self.failed_sells)} failed sells...")

            to_remove = []

            for token_mint, info in list(self.failed_sells.items()):
                input_mint = info["input_mint"]
                retries = info["retries"]

                if retries > self.max_retries:
                    logger.warning(f"🚫 Max retries exceeded for {token_mint}. Giving up.")
                    self.excel_utility.save_to_csv(
                        self.excel_utility.BOUGHT_TOKENS,
                        "failed_sells.csv",
                        {
                            "Timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                            "Token Mint": [token_mint],
                            "Input Mint": [input_mint],
                            "Reason": ["Max retries exceeded"],
                        },
                    )
                    to_remove.append(token_mint)
                    continue  

                try:
                    self.sell_and_update(token_mint, input_mint, trigger="RETRY")
                    to_remove.append(token_mint)
                except Exception as e:
                    self.failed_sells[token_mint]["retries"] += 1
                    logger.error(f"❌ Retry #{retries} failed for {token_mint}: {e}")
                time.sleep(2)

            for token in to_remove:
                self.failed_sells.pop(token, None)

    def simulated_sell_and_log(self, row, executed_price_usd, trigger="SIM_TP_SL"):
        try:
            token_mint = row["Token_bought"]
            input_mint = row["Token_sold"]
            entry_price_sol = float(row["Real_Entry_Price"] if not pd.isna(row["Real_Entry_Price"]) else row["Quote_Price"])

            sol_price_usd = float(self.solana_manager.get_token_prices([self.base_token])["data"][self.base_token]["price"])
            if "Entry_USD" in row and not pd.isna(row["Entry_USD"]):
                entry_price_usd = float(row["Entry_USD"])
            else:
                entry_price_usd = entry_price_sol * sol_price_usd

            pnl = ((executed_price_usd - entry_price_usd) / entry_price_usd) * 100

            data = {
                "Timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                "Token Mint": [token_mint],
                "Entry_USD": [entry_price_usd],
                "Exit_USD": [executed_price_usd],
                "PnL (%)": [round(pnl, 2)],
                "Sell_Signature": ["SIMULATED"],
                "Buy_Signature": [row.get("Signature", "")],
                "Type": ["SIMULATED_SELL"],
                "Trigger": [trigger]
            }

            self.excel_utility.save_to_csv(
                self.excel_utility.BOUGHT_TOKENS,
                "simulated_closed_positions.csv",
                data,
            )

            with self.tokens_lock:
                self.tokens_to_remove.add(token_mint)

            logger.info(f"✅ Simulated Sell for {token_mint} | Entry: ${entry_price_usd:.6f} | Exit: ${executed_price_usd:.6f} | PnL: {pnl:.2f}%")

        except Exception as e:
            logger.error(f"❌ Error during simulated sell: {e}")

    def has_open_positions(self):
        try:
            if not os.path.exists(self.file_path):
                return False

            df = pd.read_csv(self.file_path)
            df = df[df["type"].isin(["BUY", "SIMULATED_BUY"])]
            return not df.empty

        except Exception as e:
            logger.error(f"❌ Error checking open positions: {e}")
            return True 

    def has_failed_sells(self):
        with self.tokens_lock:
            return len(self.failed_sells) > 0
