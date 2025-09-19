import pandas as pd
import time
import os
from datetime import datetime
import threading
from helpers.bot_context import BotContext




class OpenPositionTracker:
    def __init__(self,ctx:BotContext):
        #objects
        self.ctx = ctx
        self.settings = self.ctx.settings
        self.excel_utility = self.ctx.excel_utility
        self.logger = self.ctx.logger
        self.tracker_logger = self.ctx.tracker_logger
        self.solana_manager = self.ctx.get("solana_manager")
        
        #local instances
        self.running = True
        self.base_token = "So11111111111111111111111111111111111111112"
        self.failed_sells = {}
        self.max_retries = 3
        self.tokens_to_remove = set()
        self.tokens_lock = threading.Lock()
        self.peak_price_dict = {}
        self.token_name_cache = {}
        self.token_image_cache = {}
        self.buy_timestamp = {}

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")

        
        #check bot mode
        self.file_path = os.path.join(
            self.excel_utility.OPEN_POISTIONS,
            f"simulated_tokens_{date_str}.csv" if  self.settings["SIM_MODE"] else f"open_positions_{date_str}.csv"
        )
        self.exit_checks = {
        "USE_SL": self.check_emergency_sl,       
        "USE_TP": self.check_take_profit,        
        "USE_TSL": self.check_trailing_stop,    
        "USE_TIMEOUT": self.check_timeout,       
    }

    def track_positions(self, stop_event):
        self.logger.info("📚 Starting to track open positions from Excel...")

        while not stop_event.is_set() or self.has_open_positions():
            if not os.path.exists(self.file_path):
                self.logger.debug("📭 Waiting for buy file to be created...")
                time.sleep(1)
                continue

            try:
                df = pd.read_csv(self.file_path)
                if df.empty:
                    self.logger.debug("📭 File is empty.")
                    time.sleep(5)
                    continue

                required_columns = {"Token_bought", "Token_sold", "Quote_Price", "type", "Real_Entry_Price", "Buy_Timestamp"}
                if not required_columns.issubset(df.columns):
                    self.logger.info("📄 File missing expected columns — waiting...")
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
                        self.logger.warning(f"⚠️ Failed to fetch single token prices: {e}")
                        continue
                else:
                    price_data = self.solana_manager.get_token_prices(mints)["data"]

                for _, row in df.iterrows():
                    token_mint = row["Token_bought"]
                    input_mint = row["Token_sold"]

                    if token_mint not in price_data or self.base_token not in price_data:
                        self.logger.warning(f"⚠️ Missing price data for {token_mint} or SOL.")
                        continue
                    if "Entry_USD" in row and not pd.isna(row["Entry_USD"]):
                        buy_price_usd = float(row["Entry_USD"])
                    else:
                        sol_price_usd = float(price_data[self.base_token]["price"])
                        buy_price_sol = float(row["Real_Entry_Price"] if not pd.isna(row["Real_Entry_Price"]) else row["Quote_Price"])
                        buy_price_usd = buy_price_sol * sol_price_usd

                    current_price_usd = float(price_data[token_mint]["price"])
                    buy_time = datetime.strptime(row["Buy_Timestamp"], "%Y-%m-%d %H:%M:%S")
                    self.buy_timestamp[token_mint] = buy_time
                    
                    # Extract token info with caching
                    if token_mint not in self.token_name_cache or self.token_image_cache.get(token_mint) is None:
                        try:
                            metadata = self.solana_manager.get_token_meta_data(token_mint)
                            if metadata:
                                self.token_name_cache[token_mint] = metadata.get("name", token_mint)
                                self.token_image_cache[token_mint] = metadata.get("image")
                            else:
                                # Fallbacks if API returned empty
                                self.token_name_cache[token_mint] = token_mint
                                self.token_image_cache[token_mint] = None
                        except Exception as e:
                            self.logger.debug(f"⚠️ Metadata lookup failed for {token_mint}: {e}")
                            self.token_name_cache[token_mint] = token_mint
                            self.token_image_cache[token_mint] = None


                    # Logging
                    self.logger.info(
                        f"🔎 Tracking {token_mint} | Buy: ${buy_price_usd:.10f} | Current: ${current_price_usd:.10f}"
                    )
                    self.tracker_logger.info({
                        "event": "track",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "token_mint": token_mint,
                        "input_mint":input_mint,
                        "entry_price": buy_price_usd,
                        "current_price": current_price_usd,
                        "trigger": None,
                        "pnl": ((current_price_usd - buy_price_usd) / buy_price_usd) * 100,
                        "token_name": self.token_name_cache.get(token_mint, token_mint),
                        "token_image": self.token_image_cache.get(token_mint),
                    })
                    
                    exit_rules = self.settings.get("EXIT_RULES", {})
                    for rule, func in self.exit_checks.items():
                        if exit_rules.get(rule, False):
                            result = func(token_mint, buy_price_usd, current_price_usd, buy_time)
                            if result:
                                trigger = result["trigger"]
                                self.logger.info(f"⚡ Exit triggered: {trigger} for {token_mint}")

                                if row["type"] == "SIMULATED_BUY":
                                    self.simulated_sell_and_log(token_mint, input_mint,trigger=trigger)
                                else:
                                    self.sell_and_update(token_mint, input_mint, trigger=trigger)
                                break 

                with self.tokens_lock:
                    if self.tokens_to_remove:
                        df = df[~df["Token_bought"].isin(self.tokens_to_remove)]
                        df.to_csv(self.file_path, index=False)
                        self.logger.info(f"🧼 Removed {len(self.tokens_to_remove)} tokens from open positions.")
                        self.tokens_to_remove.clear()

            except Exception as e:
                self.logger.error(f"❌ Error in OpenPositionTracker: {e}")

            time.sleep(0.25)

    def sell_and_update(self, token_mint, input_mint, trigger=None):
        try:
            result = self.solana_manager.sell(token_mint, input_mint)

            if not result["success"]:
                self.logger.warning(f"❌ Sell failed for {token_mint}. Skipping log and update.")
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
                    self.logger.warning(f"⚠️ No matching entry price found for {token_mint}")
                    return

                if "Entry_USD" in matched_row.columns and not pd.isna(matched_row.iloc[0]["Entry_USD"]):
                    entry_price_usd = float(matched_row.iloc[0]["Entry_USD"])
                else:
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
                self.logger.error(f"❌ Failed to read or convert entry price for {token_mint}: {e}")
                return

            pnl = ((executed_price_usd - entry_price_usd) / entry_price_usd) * 100
            self._finalize_sell(
                token_mint, input_mint,
                executed_price_usd, entry_price_usd, pnl,
                trigger, signature, is_sim=False,
            )
        except Exception as e:
            self.logger.error(f"❌ Exception in sell_and_update for {token_mint}: {e}")
            if token_mint not in self.failed_sells:
                self.failed_sells[token_mint] = {"input_mint": input_mint, "retries": 1}
            else:
                self.failed_sells[token_mint]["retries"] += 1
  
    def retry_failed_sells(self,stop_event):
        
        while not stop_event.is_set() or self.has_failed_sells():
            if not self.failed_sells:
                time.sleep(5)
                continue

            self.logger.info(f"🔁 Retrying {len(self.failed_sells)} failed sells...")

            to_remove = []

            for token_mint, info in list(self.failed_sells.items()):
                input_mint = info["input_mint"]
                retries = info["retries"]

                if retries > self.max_retries:
                    self.logger.warning(f"🚫 Max retries exceeded for {token_mint}. Giving up.")
                    self.excel_utility.save_to_csv(
                        self.excel_utility.FAILED_TOKENS,
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
                    self.logger.error(f"❌ Retry #{retries} failed for {token_mint}: {e}")
                time.sleep(2)

            for token in to_remove:
                self.failed_sells.pop(token, None)

    def simulated_sell_and_log(self, token_mint, input_mint, trigger=None):
        try:
            executed_price_usd = float(self.solana_manager.get_token_price(token_mint))
            
            current_df = pd.read_csv(self.file_path)
            matched_row = current_df[current_df["Token_bought"] == token_mint]

            if matched_row.empty:
                self.logger.warning(f"⚠️ No matching entry found for {token_mint}")
                return

            if "Entry_USD" in matched_row.columns and not pd.isna(matched_row.iloc[0]["Entry_USD"]):
                entry_price_usd = float(matched_row.iloc[0]["Entry_USD"])
            else:
                entry_price_sol = float(
                    matched_row.iloc[0]["Real_Entry_Price"]
                    if "Real_Entry_Price" in matched_row.columns and not pd.isna(matched_row.iloc[0]["Real_Entry_Price"])
                    else matched_row.iloc[0]["Quote_Price"]
                )
                sol_price_usd = float(self.solana_manager.get_token_prices([self.base_token])["data"][self.base_token]["price"])
                entry_price_usd = entry_price_sol * sol_price_usd

            pnl = ((executed_price_usd - entry_price_usd) / entry_price_usd) * 100
            self._finalize_sell(
            token_mint, input_mint,
            executed_price_usd, entry_price_usd, pnl,
            trigger, "SIMULATED", is_sim=True,
        )
            
        except Exception as e:
            self.logger.error(f"❌ Error during simulated sell: {e}")

    def has_open_positions(self):
            try:
                if not os.path.exists(self.file_path):
                    return False

                df = pd.read_csv(self.file_path)
                df = df[df["type"].isin(["BUY", "SIMULATED_BUY"])]
                return not df.empty

            except Exception as e:
                self.logger.error(f"❌ Error checking open positions: {e}")
                return True 

    def has_failed_sells(self):
        with self.tokens_lock:
            return len(self.failed_sells) > 0

    def check_take_profit(self, token_mint, buy_price_usd, current_price_usd, buy_time):
        tp = self.settings.get("TP", 2.0)
        if current_price_usd >= buy_price_usd * tp:
            return {"trigger": "TP"}
        return None

    def check_trailing_stop(self, token_mint, buy_price_usd, current_price_usd, buy_time):
        sl = self.settings.get("TRAILING_STOP", 0.2)
        min_trigger = self.settings.get("MIN_TSL_TRIGGER_MULTIPLIER", 1.5)

        peak_price = self.peak_price_dict.get(token_mint, buy_price_usd)
        if current_price_usd > peak_price:
            self.peak_price_dict[token_mint] = current_price_usd

        if peak_price >= buy_price_usd * min_trigger:
            trailing_stop = peak_price * (1 - sl)
            if current_price_usd <= trailing_stop:
                return {"trigger": "TSL"}
        return None

    def check_emergency_sl(self, token_mint, buy_price_usd, current_price_usd, buy_time):
        emergency_sl = self.settings.get("SL", 0.1)
        # Only if token has NOT pumped yet
        peak_price = self.peak_price_dict.get(token_mint, buy_price_usd)
        has_pumped = peak_price >= buy_price_usd * self.settings.get("MIN_TSL_TRIGGER_MULTIPLIER", 1.5)
        if not has_pumped and current_price_usd <= buy_price_usd * (1 - emergency_sl):
            return {"trigger": "SL"}
        return None

    def check_timeout(self, token_mint, buy_price_usd, current_price_usd, buy_time):
            timeout = self.settings.get("TIMEOUT_SECONDS", 30)
            threshold = self.settings.get("TIMEOUT_PROFIT_THRESHOLD", 1.03)

            try:
                seconds_since = (datetime.now() - buy_time).total_seconds()
                if seconds_since > timeout and current_price_usd < buy_price_usd * threshold:
                    return {"trigger": "TIMEOUT"}
            except Exception as e:
                self.logger.warning(f"⚠️ Could not parse Timestamp for timeout check: {e}")
            return None
    
    def _finalize_sell(self, token_mint, input_mint, executed_price_usd, entry_price_usd, pnl, trigger, signature, is_sim=False):
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")

        filename = f"simulated_closed_positions_{date_str}.csv" if is_sim else f"closed_positions_{date_str}.csv"
        row_type = "SIMULATED_SELL" if is_sim else "SOLD"

        data = {
            "Buy_Timestamp":[self.buy_timestamp[token_mint]],
            "Sell_Timestamp": [timestamp_str],
            "Token Mint": [token_mint],
            "Entry_USD": [entry_price_usd],
            "Exit_USD": [executed_price_usd],
            "PnL (%)": [round(pnl, 2)],
            "Sell_Signature": [signature],
            "Buy_Signature": [""], 
            "Type": [row_type],
            "Trigger": [trigger],
        }
        buy_time = self.buy_timestamp.get(token_mint, datetime.now())


        self.excel_utility.save_to_csv(self.excel_utility.CLOSED_POISTIONS, filename, data)

        with self.tokens_lock:
            self.tokens_to_remove.add(token_mint)
            self.peak_price_dict.pop(token_mint, None)
            self.buy_timestamp.pop(token_mint)

        self.tracker_logger.info({
            "event": "sell",
            "Sell_Timestamp": timestamp_str,
            "Buy_Timestamp":[[buy_time]],
            "token_mint": token_mint,
            "input_mint":input_mint,
            "token_name": self.token_name_cache.get(token_mint, token_mint),
            "token_image": self.token_image_cache.get(token_mint),
            "token_mint": token_mint,
            "entry_price": entry_price_usd,
            "exit_price": executed_price_usd,
            "pnl": pnl,
            "trigger": trigger,
            "signature": signature,
        })
        self.excel_utility.save_to_csv(self.excel_utility.BACKTEST_DIR, "ui_tokens.csv", data)
