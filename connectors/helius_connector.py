import time
import json
import websocket
from datetime import datetime
from helpers.framework_manager import get_payload
from config.network import HELIUS_WS
from collections import deque
import threading
from config.dex_detection_rules import DEX_DETECTION_RULES
from config.blacklist import BLACK_LIST
from helpers.bot_context import BotContext




# Track processed signatures to avoid duplicates
signature_queue = deque(maxlen=500)
signature_cache = deque(maxlen=20000)

#to clear
signature_to_token_mint = {}


known_tokens = set()



class HeliusConnector:
    def __init__(self,ctx: BotContext,stop_ws, stop_fetcher):

        #threads + rate limiters
        self.stop_ws = stop_ws
        self.stop_fetcher = stop_fetcher
        self.helius_rate_limiter = ctx.rate_limiters["helius"]


        #bot settings
        self.bot_settings = ctx.settings
        self.network = self.bot_settings["NETWORK"]
        self.max_token_age = self.bot_settings["MAX_TOKEN_AGE_SECONDS"]
        self.min_token_liquidity = self.bot_settings["MIN_TOKEN_LIQUIDITY"]
        self.trade_amount=self.bot_settings["TRADE_AMOUNT"]
        self.sim_mode = self.bot_settings["SIM_MODE"]

        #objects + keys
        self.ctx = ctx
        self.logger = self.ctx.logger
        self.logger.info("Initializing objects Helius class...")  
        self.notification_manager = self.ctx.get("notification_manager")
        self.solana_manager =  self.ctx.get("solana_manager")
        self.volume_tracker = self.ctx.get("volume_tracker")
        self.trade_counter = self.ctx.trade_counter    
        self.rug_utility = self.ctx.rug_check
        self.excel_utility = self.ctx.excel_utility
        self.requests_utility = self.ctx.helius_requests
        self.api_key = self.ctx.api_keys["helius"]
        self.dex_name = self.ctx.api_keys["dex"]     
        
        #local instances
        self.logger = self.ctx.logger
        self.transaction_timers = {}
        self.flow_timer_by_token = {} 
        
        self.logger.info("Initializing Helius WebSocket connection...")
        self.wss_url = HELIUS_WS[self.network] + self.api_key
        self.logger.info(f"🌐 Using network: {self.network}")
        self.prepare_files()
        self.id = 1

    def prepare_files(self) -> None:
        self.dex_payload = get_payload(self.dex_name)

    def fetch_transaction(self, signature: str, tx_data=None):
        self.logger.info(f"Fetching transaction details for: {signature}")
        if tx_data is None:
            try:
                tx_data = self.solana_manager.get_transaction_data(signature)
            except Exception as e:
                self.logger.error(f"❌ Error fetching transaction data: {e}")
                return
        try:
            results = tx_data.get("result", {})
            post_token_balances = results.get("meta", {}).get("postTokenBalances", [])
            token_mint = self.extract_new_mint(post_token_balances)

            if token_mint in BLACK_LIST:
                self.logger.info(f"⛔ Token {token_mint} is blacklisted — skipping.")
                return
            if token_mint in [None, "N/A"]:
                self.logger.warning(f"⚠️ Invalid token mint for TX {signature}")
                return

            logs = results.get("meta", {}).get("logMessages", [])
            self.logger.debug(f"transaction response: {tx_data}")

            if token_mint == "So11111111111111111111111111111111111111112":
                self.logger.info("⏩ Ignoring transaction: This is a SOL transaction.")
                return

            age = self.solana_manager.get_token_age(token_mint)
            if age is None:
                self.logger.warning(f"⛔ Token {token_mint} analysis took too long. Skipping.")
                self.cleanup(token_mint)
                return

            if age > self.max_token_age:
                self.logger.warning(f"⏳ Token {token_mint} is too old ({age:.2f}s) — skipping.")
                self.cleanup(token_mint)
                return

            self.logger.info(f"✅ Passed Step 6: Token {token_mint} is {age:.2f}s old.")


            if token_mint in known_tokens:
                self.logger.debug(f"⏩ Ignoring known token: {token_mint}")
                self.cleanup(token_mint)
                return
            
            

            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M:%S")

            #capture liquidity
            liquidity = self.solana_manager.analyze_liquidty(logs, token_mint, self.dex_name, results)
            


            if liquidity > self.min_token_liquidity:
                #get token marketcap
                market_cap = self.solana_manager.get_token_marketcap(token_mint)


                known_tokens.add(token_mint)
                self.excel_utility.save_to_csv(
                    self.excel_utility.TOKENS_DIR,
                    "all_tokens_found.csv",
                    {
                        "Timestamp": [f"{date_str} {time_str}"],
                        "Signature": [signature],
                        "Token Mint": [token_mint],
                        "Liquidity (Estimated)": [liquidity],
                        "MarketCap":[market_cap]
                    },
                )

                scam_safe = self.solana_manager.check_scam_functions_helius(token_mint)
                if not scam_safe:
                    self.logger.warning(f"❌ Scam check failed — skipping {token_mint}")
                    self.cleanup(token_mint)
                    return
                # Capture pool mapping before deciding to buy
                self.solana_manager.store_pool_mapping(
                    token_mint=token_mint,
                    transaction=results, 
                )

                # record swap events for volume tracking
                threading.Thread(target=self.volume_worker,args=(token_mint, signature), daemon=True).start()

                
                if self.sim_mode and not self.trade_counter.reached_limit():
                    self.logger.info(f"🧪 [SIM_MODE] Would BUY {token_mint} with ${self.trade_amount}")
                    self.solana_manager.buy(
                        "So11111111111111111111111111111111111111112",
                        token_mint,
                        self.trade_amount,
                        self.sim_mode
                    )
                    self.trade_counter.increment()
                elif not self.trade_counter.reached_limit():
                    self.solana_manager.buy(
                        "So11111111111111111111111111111111111111112",
                        token_mint,
                        self.trade_amount
                    )
                    self.trade_counter.increment()
                else:
                    self.logger.critical("💥 MAXIMUM_TRADES reached — skipping trade.")
                    signature_queue.clear()
                self.logger.info(f"🚀 LIQUIDITY passed: ${liquidity:.2f} — considering buy for {token_mint} transaction signature:{signature}")
                
                #calculate flow time
                start_time = self.flow_timer_by_token.pop(token_mint, None)
                duration = 0
                if start_time:
                    duration = time.time() - start_time
                    self.logger.info(f"🕒 Flow duration for {token_mint}: {duration:.2f} seconds")
                else:
                    self.logger.warning(f"⚠️ No start time found for {token_mint}")
                #send notification
                msg = (f"🟢 **New token detected**\n"f"`{token_mint}`\n"f"• Est. Liquidity: ${liquidity:,.2f}\n"f"• signature: `{signature}`\n"f"• 🕒 Flow duration: {duration:,.2f}\n")
                self.notification_manager.notify_text(msg,"live")
                
                t = threading.Timer(
                    60.0,
                    self.solana_manager.post_buy_delayed_check,
                    args=(token_mint, signature, liquidity, market_cap, 1)
                )
                t.daemon = True 
                t.start()



            else:
                self.logger.info("⛔ Liquidity too low — skipping.")

        except Exception as e:
            self.logger.error(f"❌ Error processing transaction logic: {e}", exc_info=True)

    def run_transaction_fetcher(self):
        while not self.stop_fetcher.is_set():
            if not signature_queue:
                time.sleep(0.4)
                continue

            self.logger.info(
                f"🔄 Fetching transactions for {len(signature_queue)} new signatures..."
            )

            while signature_queue:
                try:
                    item = signature_queue.popleft()

                    if isinstance(item, tuple):
                        signature, tx_data = item
                    else:
                        signature = item
                        tx_data = None
                    self.fetch_transaction(signature, tx_data)
                except IndexError:
                    self.logger.warning("⚠️ Attempted to pop from an empty signature queue.")
                    break

    def start_ws(self) -> None:
        """Starts the WebSocket connection to Helius RPC."""
        self.logger.info(f"Connecting to WebSocket: {self.wss_url}")

        self.ws = websocket.WebSocketApp(
            self.wss_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

        while not self.stop_ws.is_set():
            try:
                self.ws.run_forever()
            except Exception as e:
                self.logger.error(f"❌ WebSocket error: {e}")

            if self.stop_ws.is_set():
                try:
                    if self.ws:
                        self.ws.close()
                    self.logger.info("🔌 WebSocket closed due to shutdown request.")
                except Exception as e:
                    self.logger.error(f"❌ Error while closing WebSocket: {e}")
                break

            # 🔄 If not shutting down → reconnect after 5s
            self.logger.warning("WebSocket connection closed. Reconnecting in 5s...")
            time.sleep(5)

    def on_open(self, ws) -> None:
        """Subscribe to logs for new liquidity pools on solana."""
        self.logger.info(f"Subscribing to {self.dex_name} AMM logs...")
        self.dex_payload["id"] = self.id
        self.id += 1
        ws.send(json.dumps(self.dex_payload))
        self.logger.info("✅ Successfully subscribed to liquidity logs.")

    def on_message(self, ws, message) -> None:
        """Handles incoming WebSocket messages for detecting new Raydium and Pump.fun tokens on Solana."""
        try:
            if not message:
                self.logger.error("❌ Received an empty WebSocket message.")
                return

            try:
                data = json.loads(message)
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ Error decoding WebSocket message: {e}")
                return

            # Extract transaction details
            result = data.get("params", {}).get("result", {})
            context = result.get("context", {})
            value = result.get("value", {})
            slot = context.get("slot")
            signature = value.get("signature", "")
            logs = value.get("logs", [])
            error = value.get("err", None)

            self.logger.debug(f"websocket response: {data}")

            # Analyze error (if exists)
            if error is not None:
                if isinstance(error, dict) and "InstructionError" in error:
                    instr_err = error["InstructionError"][1]
                    if isinstance(instr_err, dict):
                        custom_code = instr_err.get("Custom", None)
                    else:
                        custom_code = instr_err
                    hex_code = hex(custom_code) if isinstance(custom_code, int) else "N/A"
                    self.logger.debug(
                        f"⚠️ TX failed with custom error {custom_code} (hex: {hex_code})"
                    )
            else:
                self.logger.debug(f"⚠️ TX failed with non-custom error: {error}")
            self.logger.debug(f"🔍 Raw logs for {signature}: {logs}")
            
            
            detection_rules = DEX_DETECTION_RULES.get(self.dex_name, [])
            mint_related = any(
                any(rule in log for rule in detection_rules)
                for log in logs
            )

            if not mint_related:
                self.logger.debug(f"⛔ Skipping TX: No {self.dex_name} launch indicators found.")
                return
            # Skip duplicates
            if signature in signature_cache or signature in signature_queue:
                return
            signature_cache.append(signature)

            self.logger.info(f"✅ Passed Step 1+2: Unique mint TX {signature}")

            #Fetch transaction data (just once)
            self.logger.info(f"📤 Fetching first TX data for {signature}")
            tx_data = self.solana_manager.get_transaction_data(signature)
            if not tx_data:
                self.logger.warning(f"❌ Could not fetch transaction data for: {signature}")
                return

            post_token_balances = tx_data.get("result", {}).get("meta", {}).get("postTokenBalances", [])
            token_mint = self.extract_new_mint(post_token_balances)

            if not token_mint:
                self.logger.warning(f"❌ Could not identify a new token mint in TX: {signature}")
                return

            self.logger.debug(f"🪙 postTokenBalances for {signature}: {post_token_balances}")
            self.logger.info(f"✅ Passed Step 3: Found NEW token address: {token_mint}")
            
            #start flow timer
            self._start_detection_timer(token_mint)
            self._start_flow_timer(token_mint)

            # Step 4: Add to queue with tx_data and save temporary for later to use the token address
            signature_to_token_mint[signature] = token_mint
            self.logger.debug(f"🧭 Mapped Signature → Mint: {signature} → {token_mint}")
            signature_queue.append((signature, tx_data))
            self.logger.info(f"✅ Step 4: added the token to {token_mint} ->  Signature {signature}")
            
            # Step 6: Prefetch recent txs for the same token
            try:
                txs = self.solana_manager.get_recent_transactions_signatures_for_token(token_mint)[1:5]
                if txs:
                    self.logger.info(f"📦 Found {len(txs)} early txs after mint — pre-queuing...")
                else:
                    return
                for tx_sig in txs:
                    if tx_sig in signature_cache or tx_sig in signature_queue:
                        continue
                    signature_cache.append(tx_sig)
                    signature_queue.append((tx_sig))
                    self.logger.debug(f"🧊 Queued early tx: {tx_sig}")
            except Exception as e:
                self.logger.error(f"❌ Failed to prefetch txs for {signature}: {e}")

        except Exception as e:
            self.logger.error(f"❌ Error processing WebSocket message: {e}", exc_info=True)

    def on_error(self, ws, error) -> None:
        """Handles WebSocket errors."""
        self.logger.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg) -> None:
        if self.stop_ws.is_set():
                self.logger.info("🛑 WebSocket closed and shutdown flag is set. Not reconnecting.")
                return
        self.logger.warning(f"WebSocket connection closed. Reconnecting in 5s...\ncode:{close_status_code}, msg:{close_msg}")

    def cleanup(self, token_mint):
        signature_queue_copy = list(signature_queue)
        signature_queue.clear()

        for item in signature_queue_copy:
            if isinstance(item, tuple):
                signature, tx_data = item
            else:
                signature = item
                tx_data = None

            if signature_to_token_mint.get(signature) != token_mint:
                signature_queue.append((signature, tx_data)) 

        removed = 0
        for sig, mint in list(signature_to_token_mint.items()):
            if mint == token_mint:
                signature_to_token_mint.pop(sig, None)
                removed += 1

        self.logger.info(f"🧹 Cleaned up {removed} signatures for token {token_mint}")
            
    def extract_new_mint(self, post_balances):
        for b in post_balances:
            mint = b.get("mint")
            if mint and mint != "So11111111111111111111111111111111111111112":
                return mint
        return None
   
    def _start_flow_timer(self,token_mint):
        if token_mint not in self.flow_timer_by_token:
            self.flow_timer_by_token[token_mint] = time.time()

    def _start_detection_timer(self, token_mint: str):
        if token_mint not in self.transaction_timers:
            self.transaction_timers[token_mint] = time.time()
    
    def close(self):
        """Stop reconnect loop and close WebSocket immediately."""
        self.stop_ws.set()       # tell loop not to reconnect
        if hasattr(self, "ws") and self.ws:
            try:
                self.ws.close()  # forces run_forever() to return
                self.logger.info("🔌 WebSocket manually closed.")
            except Exception as e:
                self.logger.error(f"❌ Error closing WebSocket: {e}")

    def volume_worker(self, token_mint, signature):
        signatures = self.solana_manager.get_recent_transactions_signatures_for_token(
            token_mint=token_mint, before=signature
        )
        try:
            snap_volumes = self.solana_manager.parse_helius_swap_volume(signatures=signatures)

            # aggregate all mints into one "total" volume
            agg_buy  = sum(v.get("buy_usd", 0.0) for v in snap_volumes.values())
            agg_sell = sum(v.get("sell_usd", 0.0) for v in snap_volumes.values())
            aggregated = {
                "buy_usd": agg_buy,
                "sell_usd": agg_sell,
                "total_usd": agg_buy + agg_sell,
            }

            self.volume_tracker.record_trade(token_mint, aggregated, signature)

            self.volume_tracker.snapshot_launch(
                token_mint,
                timestamp=time.time(),
                first_trade_usd=aggregated["total_usd"],
                signature=signature,
            )

            self.logger.info(f"📊 Volume snapshot recorded for {token_mint}")

        except Exception as e:
            self.logger.error(f"❌ Volume snapshot failed for {token_mint}: {e}", exc_info=True)

