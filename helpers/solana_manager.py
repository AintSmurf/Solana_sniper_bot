from solana.rpc.api import Client
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore
from solders.message import MessageV0  # type: ignore
from spl.token.instructions import create_associated_token_account,get_associated_token_address
from config.third_parties import JUPITER_STATION
from config.network import HELIUS_URL
import struct
from solana.transaction import Transaction
from config.third_parties import JUPITER_STATION
from helpers.framework_manager import get_payload
import base64
import math
import requests
from datetime import datetime
import re
import time
from spl.token.constants import TOKEN_PROGRAM_ID as SPL_TOKEN_PROGRAM_ID
from config.dex_detection_rules import PUMPFUN_PROGRAM_ID,RAYDIUM_PROGRAM_ID,KNOWN_BASES
import threading
from helpers.bot_context import BotContext
from concurrent.futures import ThreadPoolExecutor, as_completed






class SolanaManager:
    def __init__(self,ctx:BotContext):
        #objects
        self.ctx = ctx
        self.settings = self.ctx.settings
        self.helius_requests = self.ctx.helius_requests
        self.jupiter_requests = self.ctx.jupiter_requests
        self.helius_enhanced =self.ctx.helius_enhanced
        self.rug_check_utility = self.ctx.rug_check
        self.excel_utility = self.ctx.excel_utility
        self.volume_tracker = self.ctx.get("volume_tracker")
        self.notification_manager = self.ctx.get("notification_manager")

        #self.logger
        self.logger =self.ctx.logger
        self.special_logger =self.ctx.special_logger

        #rate limits        
        self.helius_rate_limiter = self.ctx.rate_limiters["helius"]
        self.jupiter_rate_limiter = self.ctx.rate_limiters["jupiter"]

        self.prepare_json_files()
        #environmint variblies
        self.api_key = self.ctx.api_keys["helius"]
        self._private_key_solana = self.ctx.api_keys["wallet_key"]
        self.bird_api_key = self.ctx.api_keys["bird_eye"]

        #wallet
        self.logger.info("Initializing wallet solana manager class...") 
        self.url = HELIUS_URL[self.ctx.settings["NETWORK"]] + self.api_key
        self.client = Client(self.url, timeout=30)
        self.keypair = Keypair.from_base58_string(self._private_key_solana)
        self.wallet_address = self.keypair.pubkey()
        self.logger.debug(
            f"Initialized TransactionHandler with wallet: {self.wallet_address}"
        )
        self.id = 1

        #local instances
        self.slippage = float(self.settings["SLPG"])
        self._cached_sol_price = None
        self._last_sol_fetch = 0
        self._sol_cache_ttl = 5
        self.token_pools = {}
    
    def prepare_json_files(self):
        self.transaction_simulation_paylod = get_payload("Transaction_simulation")
        self.swap_payload = get_payload("Swap_token_payload")
        self.liquidity_payload = get_payload("Liquidity_payload")
        self.send_transaction_payload = get_payload("Send_transaction")
        self.asset_payload = get_payload("Asset_payload")
        self.largest_accounts_payload = get_payload("Largets_accounts")
        self.program_accounts = get_payload("Liquidity_payload")
        self.token_account_by_owner = get_payload("Token_account_by_owner")
        self.transaction_payload = get_payload("Transaction")
        self.signature_for_adress = get_payload("Signature_for_adress")
        self.block_time_payload = get_payload("Blocktime_payload")
        self.helius_multiple_transactions = get_payload("Enhanced transactions")

    def get_account_balances(self) -> list:
        self.logger.debug(f"Fetching token balances for wallet: {self.wallet_address}")

        try:
            # Call your existing Helius wrapper
            accounts = self.get_token_accounts_by_owner(str(self.wallet_address))

            token_balances = []
            for acc in accounts:
                try:
                    mint = acc.get("mint")
                    amount = int(acc.get("amount", 0))
                    decimals = int(acc.get("decimals", 0))
                    balance = amount / (10 ** decimals) if decimals > 0 else amount

                    token_balances.append({
                        "token_mint": mint,
                        "balance": balance
                    })
                except Exception as inner_e:
                    self.logger.error(f"❌ Error processing token account {acc}: {inner_e}")

            # Add SOL balance
            try:
                sol_balance_response = self.client.get_balance(self.wallet_address)
                sol_balance = sol_balance_response.value / (10 ** 9)
                token_balances.insert(0, {"token_mint": "SOL", "balance": sol_balance})
            except Exception as sol_e:
                self.logger.warning(f"⚠️ Could not fetch SOL balance: {sol_e}")

            # Optionally filter out zero balances
            token_balances = [b for b in token_balances if b["balance"] > 0]

            self.logger.info(f"✅ Retrieved {len(token_balances)} token balances.")
            self.logger.debug(f"Token Balances: {token_balances}")

            return token_balances

        except Exception as e:
            self.logger.error(f"❌ Failed to fetch balances: {e}")
            return []

    def add_token_account(self, token_mint: str):
        """Ensure the wallet has an Associated Token Account (ATA) for a given token."""
        self.logger.debug(f"Checking token account for mint: {token_mint}")

        try:
            token_mint_pubkey = Pubkey.from_string(token_mint)
            associated_token_account = get_associated_token_address(
                owner=self.wallet_address, mint=token_mint_pubkey
            )

            response = self.client.get_account_info(associated_token_account)
            self.logger.debug(f"Token Account Lookup Response: {response}")

            if response.value:
                self.logger.info(
                    f"✅ Token account already exists: {associated_token_account}"
                )
                return associated_token_account

            self.logger.info(f"Creating new token account for mint: {token_mint}")

            transaction = Transaction()
            transaction.add(
                create_associated_token_account(
                    payer=self.wallet_address,
                    owner=self.wallet_address,
                    mint=token_mint_pubkey,
                )
            )

            blockhash_resp = self.client.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash

            message = MessageV0.try_compile(
                self.wallet_address, transaction.instructions, [], recent_blockhash
            )
            versioned_txn = VersionedTransaction(message, [self.keypair])

            send_response = self.client.send_transaction(versioned_txn)

            if send_response.value:
                self.logger.info(f"✅ Token account created: {associated_token_account}")
                self.logger.debug(f"Transaction Signature: {send_response.value}")
                return associated_token_account
            else:
                self.logger.warning(
                    f"⚠️ Token account creation might have failed: {send_response}"
                )
                return None

        except Exception as e:
            self.logger.error(f"❌ Failed to create token account: {e}")
            return None

    def buy(self, input_mint: str, output_mint: str, usd_amount: int, sim: bool = False) -> str:

        self.logger.info(f"🔄 Initiating buy for ${usd_amount} — Token: {output_mint}")
        try:
            token_amount = self.get_solana_token_worth_in_dollars(usd_amount)       
            quote = self.get_quote(input_mint, output_mint, token_amount,self.slippage)
            if not quote:
                self.logger.warning("⚠️ No quote received, aborting buy.")
                return None

            self.logger.info(f"📦 Jupiter Quote for{output_mint}: In = {quote['inAmount']}, Out = {quote['outAmount']}")
            
            input_decimals = self.get_token_decimals(input_mint)
            output_decimals = self.get_token_decimals(output_mint)

            normalized_in = float(quote["inAmount"]) / (10 ** input_decimals)
            normalized_out = float(quote["outAmount"]) / (10 ** output_decimals)

            quote_price = normalized_out / normalized_in

            self.logger.info(f"💡 Expected quote price for{output_mint}: {quote_price:.10f}")
            
            #default data        
            now = datetime.now()
            timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
            date_str = now.strftime("%Y-%m-%d")

            data = {
                "Buy_Timestamp": [timestamp_str],
                "Quote_Price": [quote_price],
                "Token_sold": [input_mint],
                "Token_bought": [output_mint],
            }
            token_decimals = self.get_token_decimals(output_mint)
            token_received = float(quote["outAmount"]) / (10 ** token_decimals)
            if token_received == 0:
                self.logger.warning(f"❌ Quote gives 0 tokens, skipping simulation for {output_mint}")
                return None

            real_entry_price = usd_amount / token_received 
            if sim: 

                data.update({
                    "type": ["SIMULATED_BUY"],
                    "Real_Entry_Price": [real_entry_price], 
                    "Token_Received": [token_received],
                    "WSOL_Spent": [0],
                    "Sold_At_Price": [0],
                    "SentToDiscord": [False],
                    "Signature": ["SIMULATED"],
                    "Entry_USD": [real_entry_price], 
                })
                self.excel_utility.save_to_csv(self.excel_utility.NOTIFICATIONS, f"discord_{date_str}.csv", data)
                self.excel_utility.save_to_csv(self.excel_utility.OPEN_POISTIONS, f"simulated_tokens_{date_str}.csv", data)
                return "SIMULATED"


            # 🚀 Send transaction
            txn_64 = self.get_swap_transaction(quote)
            self.send_transaction_payload["params"][0] = txn_64
            self.send_transaction_payload["id"] = self.id
            self.id += 1
            self.helius_rate_limiter.wait()
            response = self.helius_requests.post(
                self.api_key, payload=self.send_transaction_payload
            )
            self.logger.debug(f"Buy response: {response}")
            
            
            buy_signature = response.get("result", None)
            if "result" not in response:
                self.logger.warning(f"❌ Buy FAILED for {output_mint}: {response['error'].get('message')}")
                data.update({
                    "type": ["FAILED_BUY"],
                    "Error_Code": [response["error"]["code"]],
                    "Error_Message": [response["error"]["message"]],
                })
                self.excel_utility.save_to_csv(self.excel_utility.FAILED_TOKENS, f"failed_buys_{date_str}.csv", data)
                return None
            threading.Thread(
                target=self.verify_signature,
                args=(buy_signature, data, date_str, output_mint, "BUY"),
                daemon=True
            ).start()

            self.logger.info(f"✅ Buy SUCCESSFUL for {output_mint}")


            data.update({
                "Real_Entry_Price": [real_entry_price],
                "Entry_USD": [real_entry_price],
                "Token_Received": [token_received],
                "WSOL_Spent": [usd_amount / self.get_sol_price()],
                "type": ["PENDING"],
                "Sold_At_Price": [0],
                "SentToDiscord": [False],
                "Signature": [buy_signature],
            })

            # Save instantly so tracker can pick it up
            self.excel_utility.save_to_csv(self.excel_utility.OPEN_POISTIONS, f"bought_tokens_{date_str}.csv", data)
            self.excel_utility.save_to_csv(self.excel_utility.OPEN_POISTIONS, f"open_positions_{date_str}.csv", data)
            self.excel_utility.save_to_csv(self.excel_utility.NOTIFICATIONS, f"discord_{date_str}.csv", data)

            # Spawn async updater for true balance
            threading.Thread(
                target=self._update_entry_price_with_balance,
                args=(output_mint, usd_amount, date_str,  data),
                daemon=True
            ).start()

            return buy_signature

        except Exception as e:
            self.logger.error(f"❌ Exception during buy: {e}")
            return None

    def get_sol_price(self) -> float:
        now = time.time()
        if self._cached_sol_price and (now - self._last_sol_fetch < self._sol_cache_ttl):
            return self._cached_sol_price
        self.jupiter_rate_limiter.wait()
        response = self.jupiter_requests.get(
            "/price/v2?ids=So11111111111111111111111111111111111111112"
        )

        price = float(
            response["data"]["So11111111111111111111111111111111111111112"]["price"]
        )
        self._cached_sol_price = price
        self._last_sol_fetch = now
        return price

    def get_token_price_paid(self, token_mint: str) -> float:
        url = f"https://public-api.birdeye.so/defi/price?include_liquidity=true&address={token_mint}"

        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": self.bird_api_key["BIRD_EYE"],
        }
        response = requests.get(url, headers=headers)
        self.logger.debug(f"response: {response.json()}")
        return response.json()["data"]["value"]

    def get_solana_token_worth_in_dollars(self, usd_amount: int) -> float:
        sol_price = float(self.get_sol_price())
        sol_amount_needed = usd_amount / sol_price
        converted_tokens = int(sol_amount_needed * 10**9)
        return converted_tokens

    def get_token_worth_in_usd(self, token_mint: str, usd_amount: int):
        try:
            solana_tokens = self.get_solana_token_worth_in_dollars(usd_amount)
            token_quote = self.get_quote(
                "So11111111111111111111111111111111111111112", token_mint, solana_tokens
            )

            if "outAmount" not in token_quote:
                raise ValueError(f"❌ Failed to get token quote for {token_mint}")

            raw_token_amount = int(token_quote["outAmount"])

            # ✅ Step 1: Fetch the token's decimals
            token_decimals = self.get_token_decimals(token_mint)

            # ✅ Step 2: Convert the raw amount to real token amount
            token_amount = math.ceil(raw_token_amount / (10**token_decimals))

            return token_amount

        except Exception as e:
            self.logger.error(f"❌ Error getting token worth in USD: {e}")
            return None

    def get_quote(self, input_mint, output_mint, amount=1000, slippage=1):
        try:
            slippage_bps = int(slippage * 100)
            self.jupiter_rate_limiter.wait()
            quote_url = f"{JUPITER_STATION['QUOTE_ENDPOINT']}?inputMint={input_mint}&outputMint={output_mint}&amount={amount}&slippageBps={slippage_bps}&restrictIntermediateTokens=true"
            quote_response = self.jupiter_requests.get(quote_url)

            if "error" in quote_response:
                self.logger.warning(f"⚠️ Quote attempt failed: {quote_response['error']}")
                return None

            self.logger.info(f"✅ Successfully retrieved quote.")
            self.logger.debug(f"Build swap transaction: {quote_response} Success.")
            return quote_response

        except Exception as e:
            self.logger.error(f"❌ Error retrieving quote: {e}")
            return None

    def get_swap_transaction(self, quote_response: dict):
        """Get a swap transaction from Jupiter API (Raydium/Orca)"""
        if not quote_response or "error" in quote_response:
            self.logger.error(f"❌ There is an error in quote: {quote_response}")
            return None

        try:
            self.jupiter_rate_limiter.wait()
            self.swap_payload["userPublicKey"] = str(self.keypair.pubkey())
            self.swap_payload["quoteResponse"] = quote_response

            swap_response = self.jupiter_requests.post(
                endpoint=JUPITER_STATION["SWAP_ENDPOINT"], payload=self.swap_payload
            )

            if "error" in swap_response:
                self.logger.warning(
                    f"⚠️ Error getting swap transaction: {swap_response['error']}"
                )
                return None

            swap_txn_base64 = swap_response["swapTransaction"]

            try:
                raw_bytes = base64.b64decode(swap_txn_base64)
                self.logger.info(f"✅ Swap transaction decoded successfully")
                raw_tx = VersionedTransaction.from_bytes(raw_bytes)
                signed_tx = VersionedTransaction(raw_tx.message, [self.keypair])
                self.logger.debug(
                    f"Signed transaction: {signed_tx}, Wallet address: {self.wallet_address}"
                )
                self.logger.info(
                    f"Signed transaction for Wallet address: {self.wallet_address}"
                )
                seralized_tx = bytes(signed_tx)
                signed_tx_base64 = base64.b64encode(seralized_tx).decode("utf-8")
                self.logger.debug(f"signed base64 transaction: {signed_tx_base64}")
                self.logger.info(f"signed base64 transaction")
                try:
                    tx_signature = str(signed_tx.signatures[0])
                    self.logger.info(f"Transaction signature: {tx_signature}")
                except Exception as e:
                    self.logger.error(f"❌ Transaction signature extraction failed: {e}")
                    tx_signature = None

            except Exception as e:
                self.logger.error(f"❌ Swap transaction is not valid Base64: {e}")
                return None

            return signed_tx_base64

        except Exception as e:
            self.logger.error(f"❌ Error building swap transaction: {e}")
            return None

    def simulate_transaction(self, transaction_base64):
        """Simulate a transaction using Helius RPC"""
        self.transaction_simulation_paylod["params"][0] = transaction_base64
        try:
            self.helius_rate_limiter.wait()
            response = self.helius_requests.post(
                endpoint=self.api_key,
                payload=self.transaction_simulation_paylod,
            )
            self.logger.debug(f"Transaction Simulation Response: {response}")

            # Check if "error" exists in response
            if "error" in response:
                self.logger.warning(f"⚠️ Simulation failed: {response['error']}")
                self.logger.error(
                    f"simulation result: {response.get('result', 'No result')}"
                )
                return False

            # Check if "err" exists inside response["result"]["value"]
            err = response.get("result", {}).get("value", {}).get("err")
            if err is not None:
                self.logger.warning(f"⚠️ Simulation failed with error: {err}")
                return False  # Now correctly detects failure

            self.logger.info("✅ Transaction simulation successful!")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error simulating transaction: {e}")
            return False

    def get_token_decimals(
        self,
        token_mint: str,
    ) -> int:
        try:
            token_mint = Pubkey.from_string(token_mint)
            response = self.client.get_token_supply(token_mint)

            if response.value.decimals:
                return math.ceil(response.value.decimals)
            else:
                self.logger.warning(
                    f"⚠️ Failed to retrieve decimals for {token_mint}, defaulting to 6."
                )
                return 6

        except Exception as e:
            self.logger.error(f"❌ Error getting token decimals: {e}")
            return 6

    def get_token_supply(self, mint_address: str) -> float:
        """Fetch total token supply from Solana RPC and scale it correctly."""
        try:
            token_mint = Pubkey.from_string(mint_address)
            response = self.client.get_token_supply(token_mint)
            if response.value:
                supply = float(response.value.ui_amount)
                return supply

        except Exception as e:
            print(f"❌ Error fetching token supply: {e}")

        return 0

    def get_token_marketcap(self, token_mint: str) -> float:
        try:
            price = self.get_token_price(token_mint)
            supply = self.get_token_supply(token_mint)
            market_cap = price* supply
            return market_cap
        except Exception as e:
            self.logger.error("Not Legit token")

    def sell(self, input_mint: str, output_mint: str) -> dict:
        self.logger.info(f"🔄 Initiating sell order: Selling {input_mint} for {output_mint}")

        try:
            # 1. Get token balance
            balances = self.get_account_balances()
            token_info = next((t for t in balances if t["token_mint"] == input_mint), None)
            if not token_info or token_info["balance"] <= 0:
                self.logger.warning(f"⚠️ No balance found for token: {input_mint}")
                return {"success": False, "executed_price": 0.0, "signature": ""}

            decimals = self.get_token_decimals(input_mint)
            raw_amount = int(token_info["balance"] * (10 ** decimals))

            # 2. Get quote
            quote = self.get_quote(input_mint, output_mint, raw_amount,self.slippage)
            if not quote:
                self.logger.warning("⚠️ Failed to get quote.")
                return {"success": False, "executed_price": 0.0, "signature": ""}

            # 3. Execute transaction
            txn_64 = self.get_swap_transaction(quote)
            self.send_transaction_payload["params"][0] = txn_64
            self.send_transaction_payload["id"] = self.id
            self.id += 1

            self.helius_rate_limiter.wait()
            response = self.helius_requests.post(
                self.api_key, payload=self.send_transaction_payload
            )
            signature = response["result"]
            
            # if not self.verify_signature(signature):
            #     return {"success": False, "executed_price": 0.0, "signature": ""}

            
            self.logger.info(f"✅ Sell completed: Signature: {signature}")

            # 4. Calculate executed price from quote
            executed_price = float(quote["outAmount"]) / float(quote["inAmount"])

            return {
                "success": True,
                "executed_price": executed_price,
                "signature": signature,
            }

        except Exception as e:
            self.logger.error(f"❌ Exception during sell: {e}")
            return {"success": False, "executed_price": 0.0, "signature": ""}

    def is_token_scam(self, response_json, token_mint) -> bool:

        # Check if a swap route exists
        if "routePlan" not in response_json or not response_json["routePlan"]:
            self.logger.warning(f"🚨 No swap route for {token_mint}. Possible honeypot.")
            return True

        best_route = response_json["routePlan"][0]["swapInfo"]
        in_amount = float(best_route["inAmount"])
        out_amount = float(best_route["outAmount"])
        fee_amount = float(best_route["feeAmount"])

        fee_ratio = fee_amount / in_amount if in_amount > 0 else 0
        if fee_ratio > 0.05:
            self.logger.warning(
                f"⚠️ High tax detected ({fee_ratio * 100}%). Possible scam token."
            )
            return True

        self.logger.info("token scam test - tax check passed")

        if out_amount == 0:
            self.logger.warning(
                f"🚨 Token has zero output in swap! No liquidity detected for {token_mint}."
            )
            return True

        self.logger.info("token scam test - output check passed")

        if in_amount / out_amount > 10000:
            self.logger.warning(
                f"⚠️ Unreasonable token price ratio for {token_mint}. Possible rug."
            )
            return True

        self.logger.info("token scam test - price ratio check passed")
        self.logger.info(f"✅ Token {token_mint} passed Jupiter scam detection.")
        return False
    # paid version of liquidty and accurate
    def get_liqudity(self, new_token_mint: str) -> float:
        try:
            url = f"https://public-api.birdeye.so/defi/price?include_liquidity=true&address={new_token_mint}"

            headers = {
                "accept": "application/json",
                "x-chain": "solana",
                "X-API-KEY": self.bird_api_key["BIRD_EYE"],
            }
            response = requests.get(url, headers=headers)
            self.logger.info(response.json())
            self.logger.debug(f"response: {response.json()}")
            return response.json()["data"]["liquidity"]

        except Exception as e:
            self.logger.error(f"failed to retrive liquidity: {e}")

        return None
    # For Raydium-based logs
    def parse__raydium_liquidity_logs(self, logs: list[str], token_mint: str, transaction: dict) -> dict:
        result = {
            "itsa": None,
            "yta": None,
            "itsa_decimals": 6,
            "yta_decimals": 9,
            "source": None,
            "itsa_mint": None,
        }

        for log in logs:
            self.logger.debug(f"🔍 Log line: {log}")

            if result["itsa"] is None:
                itsa_match = re.search(r"itsa[:=]?\s*([0-9]+)", log)
                if itsa_match:
                    result["itsa"] = int(itsa_match.group(1))
                    result["source"] = "strategy"

            if result["yta"] is None:
                yta_match = re.search(r"yta[:=]?\s*([0-9]+)", log)
                if yta_match:
                    result["yta"] = int(yta_match.group(1))
                    result["source"] = "strategy"

            if "initialize" in log and ("init_pc_amount" in log or "init_coin_amount" in log):
                self.logger.debug(f"🔍 Raydium init log: {log}")
                pc_match = re.search(r"init_pc_amount:\s*([0-9]+)", log)
                coin_match = re.search(r"init_coin_amount:\s*([0-9]+)", log)

                if pc_match:
                    result["itsa"] = int(pc_match.group(1))
                    result["itsa_decimals"] = 9
                    result["source"] = "raydium"

                if coin_match:
                    result["yta"] = int(coin_match.group(1))
                    result["source"] = "raydium"

        # ✅ Fallback: Token balances
        if (
            (result["yta"] is None or result["yta"] == 0 or result["itsa"] is None or result["itsa"] == 0)
            and "postTokenBalances" in transaction.get("meta", {})
        ):
            for balance in transaction["meta"]["postTokenBalances"]:
                mint = balance.get("mint")
                amount = int(balance["uiTokenAmount"]["amount"])
                decimals = balance["uiTokenAmount"]["decimals"]

                if mint == token_mint and (result["yta"] is None or result["yta"] == 0):
                    result["yta"] = amount
                    result["yta_decimals"] = decimals
                elif mint != token_mint and (result["itsa"] is None or result["itsa"] == 0):
                    result["itsa"] = amount
                    result["itsa_decimals"] = decimals
                    result["itsa_mint"] = mint
                    result["source"] = "raydium"
        return self._calculate_liquidity(result, token_mint)
    # For Pump.fun-based logs
    def parse__pumpfun_liquidity_logs(self, logs: list[str], token_mint: str, transaction: dict) -> dict:
        result = {
            "itsa": None,
            "yta": None,
            "itsa_decimals": 9,  # Lamports (SOL)
            "yta_decimals": 9,
            "source": "pumpfun",
            "itsa_mint": None,
        }

        # 🔍 Try to extract from logs
        for log in logs:
            if "SwapEvent" in log or "Instruction: Buy" in log:
                result["source"] = "pumpfun"

                swap_match = re.search(r"amount_in\s*:\s*([0-9]+),\s*amount_out\s*:\s*([0-9]+)", log)
                if swap_match:
                    result["itsa"] = int(swap_match.group(1))
                    result["yta"] = int(swap_match.group(2))

            if result["itsa"] is None:
                match_in = re.search(r"amount_in\s*:\s*([0-9]+)", log)
                if match_in:
                    result["itsa"] = int(match_in.group(1))

            if result["yta"] is None:
                match_out = re.search(r"amount_out\s*:\s*([0-9]+)", log)
                if match_out:
                    result["yta"] = int(match_out.group(1))
            if result["itsa"] is not None and result["yta"] is not None:
                return self._calculate_liquidity(result, token_mint) 

        # ✅ Fallback outside the log loop
        if (
            (result["yta"] is None or result["yta"] == 0 or result["itsa"] is None or result["itsa"] == 0)
            and "postTokenBalances" in transaction.get("meta", {})
        ):
            for balance in transaction["meta"]["postTokenBalances"]:
                mint = balance.get("mint")
                amount = int(balance["uiTokenAmount"]["amount"])
                decimals = balance["uiTokenAmount"]["decimals"]

                if mint == token_mint and (result["yta"] is None or result["yta"] == 0):
                    result["yta"] = amount
                    result["yta_decimals"] = decimals
                elif mint != token_mint and (result["itsa"] is None or result["itsa"] == 0):
                    result["itsa"] = amount
                    result["itsa_decimals"] = decimals
                    result["itsa_mint"] = mint
        return self._calculate_liquidity(result, token_mint)
    # Shared liquidity post-processing
    def _calculate_liquidity(self, result: dict, token_mint: str) -> dict:
        if result["itsa"] is not None and result["yta"] is not None:
            try:
                result["yta_decimals"] = self.get_token_decimals(token_mint)
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to fetch decimals for {token_mint}: {e}")
                result["yta_decimals"] = 9

            # Known base mints
            KNOWN_BASES = {
                "So11111111111111111111111111111111111111112": {"decimals": 9, "symbol": "SOL"},
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {"decimals": 6, "symbol": "USDC"},
                "Es9vMFrzaCERc1eZqDum62vD9BTezVXNid1QH2G2Vw5B": {"decimals": 6, "symbol": "USDT"},
            }

            itsa_mint = result.get("itsa_mint")
            itsa_decimals = result["itsa_decimals"]
            itsa_amount = result["itsa"] / (10 ** itsa_decimals)
            itsa_usd = 0

            if result["source"] in ["raydium", "pumpfun"]:
                if itsa_mint in KNOWN_BASES:
                    base_symbol = KNOWN_BASES[itsa_mint]["symbol"]
                    if base_symbol == "SOL":
                        try:
                            sol_price = self.get_sol_price()
                            itsa_usd = itsa_amount * sol_price
                        except Exception as e:
                            self.logger.warning(f"⚠️ Failed to fetch SOL price: {e}")
                            itsa_usd = 0
                    elif base_symbol in {"USDC", "USDT"}:
                        itsa_usd = itsa_amount  # Already USD
                else:
                    # fallback if base mint is unknown
                    self.logger.warning(f"⚠️ Unknown base mint for ITSA: {itsa_mint}, assuming USD = 0")
                    itsa_usd = 0

            yta_tokens = result["yta"] / (10 ** result["yta_decimals"])

            result["liquidity_usd"] = itsa_usd
            result["token_amount"] = yta_tokens
            result["launch_price_usd"] = round(itsa_usd / yta_tokens, 8) if yta_tokens > 0 else 0

            self.logger.debug(
                f"🧪 Liquidity calc for {token_mint} | itsa: {result['itsa']} "
                f"| yta: {result['yta']} | USD: {result.get('liquidity_usd', 0)}"
            )

        return result
    # helper free version of liquidity and estmiated
    def analyze_liquidty(self, logs: list[str], token_mint: str, dex: str, transaction):
        if dex.lower() == "raydium":
            liquidity_data = self.parse__raydium_liquidity_logs(logs, token_mint, transaction)
        elif dex.lower() == "pumpfun":
            liquidity_data = self.parse__pumpfun_liquidity_logs(logs, token_mint, transaction)
        else:
            self.logger.warning(f"Unknown DEX: {dex}")
            return 0

        if liquidity_data.get("liquidity_usd", 0) > 0:
            liquidity = liquidity_data["liquidity_usd"]
            launch_price = liquidity_data["launch_price_usd"]
            self.logger.info(
                f"💧 Liquidity detected for {token_mint} - ${liquidity:.2f}, Launch price: ${launch_price:.8f}"
            )
            return liquidity
        else:
            self.logger.info("ℹ️ No liquidity info found in logs.")
            return 0

    def get_token_prices(self, mints: list) -> dict:
        ids = ",".join(mints)
        self.jupiter_rate_limiter.wait()
        endpoint = f"{JUPITER_STATION['PRICE']}?ids={ids}&showExtraInfo=true"
        return self.jupiter_requests.get(endpoint)

    def get_token_price(self, mint: str) -> float:
        self.jupiter_rate_limiter.wait()
        endpoint = f"{JUPITER_STATION['PRICE']}?ids={mint}&showExtraInfo=true"
        data = self.jupiter_requests.get(endpoint)
        return float(data["data"][mint]["price"])
    
    def post_buy_delayed_check(self, token_mint, signature, liquidity, market_cap, attempt=1):
        self.logger.info(f"⏳ Running DELAYED post-buy check (attempt {attempt}) for {token_mint}...")

        results = {
            "LP_Check": "FAIL",
            "Holders_Check": "FAIL",
            "Volume_Check": "FAIL",
            "MarketCap_Check": "FAIL",
        }
        score = 0
        # LP lock ratio
        try:
            lp_status = self.rug_check_utility.is_liquidity_unlocked_test(token_mint)
            if lp_status == "safe":
                results["LP_Check"] = "PASS"
                score += 1
            elif lp_status == "risky":
                results["LP_Check"] = "RISKY"
                score += 0.5
        except Exception as e:
            self.logger.error(f"❌ LP check failed for {token_mint}: {e}")

        # Holder distribution
        try:
            if self.get_largest_accounts(token_mint):
                results["Holders_Check"] = "PASS"
                score += 1
        except Exception as e:
            self.logger.error(f"❌ Holder distribution check failed for {token_mint}: {e}")

        # Volume growth since launch
        try:
            launch_info = self.volume_tracker.token_launch_info.get(token_mint, {})
            first_sig = launch_info.get("first_signature")

            signatures = self.get_recent_transactions_signatures_for_token(
                token_mint=token_mint,
                until=first_sig 
            )

            snap_volumes = self.parse_helius_swap_volume(signatures=signatures)

            for mint, v in snap_volumes.items():
                self.volume_tracker.record_trade(
                    mint,
                    {
                        "buy_usd": v.get("buy_usd", 0.0),
                        "sell_usd": v.get("sell_usd", 0.0),
                        "total_usd": v.get("total_usd", 0.0),
                    },
                    signature="post_buy"
                )

            stats = self.volume_tracker.stats(token_mint, window=999999)

            if stats["total_usd"] > launch_info.get("launch_volume", 0.0) and stats["buy_usd"] > stats["sell_usd"]:
                self.logger.info(f'poassed volume test launch volume:{launch_info.get("launch_volume", 0.0)} current volume: {stats["total_usd"] }')
                results["Volume_Check"] = "PASS"
            else:
                results["Volume_Check"] = (
                    f"FAIL (Now ${stats['total_usd']:.2f}, "
                    f"Buys ${stats['buy_usd']:.2f} vs Sells ${stats['sell_usd']:.2f})"
                )

        except Exception as e:
            self.logger.error(f"❌ Volume check failed for {token_mint}: {e}")

        # Market cap
        try:
            if market_cap and market_cap <= 1_000_000:
                results["MarketCap_Check"] = "PASS"
                score += 1
        except Exception as e:
            self.logger.error(f"❌ Market cap check failed for {token_mint}: {e}")

        self.logger.info(
            f"📊 Token {token_mint} scored {score}/4 | "
            f"LP={results['LP_Check']} | Holders={results['Holders_Check']} | "
            f"Volume={results['Volume_Check']} | MarketCap={results['MarketCap_Check']}"
        )

        # Save results to CSV
        try:
            self.excel_utility.save_to_csv(
                self.excel_utility.BACKTEST_DIR,
                "post_buy_checks.csv",
                {
                    "Timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                    "Signature": [signature],
                    "Token Mint": [token_mint],
                    "Liquidity (Estimated)": [liquidity],
                    "Market Cap": [market_cap],
                    "Score": [score],
                    "LP_Check": [results["LP_Check"]],
                    "Holders_Check": [results["Holders_Check"]],
                    "Volume_Check": [results["Volume_Check"]],
                    "MarketCap_Check": [results["MarketCap_Check"]],

                # 🔹 Volume essentials
                "Current Buys": [stats["buy_usd"]],
                "Current Sells": [stats["sell_usd"]],
                "Current Volume": [stats["total_usd"]],
                },
            )
        except Exception as e:
            self.logger.error(f"❌ Failed to save post-buy checks for {token_mint}: {e}")

        return {"score": score, "results": results}

    def check_scam_functions_helius(self, token_mint: str) -> bool:
        # get token worth in usd so it wont fail the jupiter
        token_amount = self.get_solana_token_worth_in_dollars(15)
        qoute = self.get_quote(
            token_mint, "So11111111111111111111111111111111111111112", token_amount
        )
        if not qoute:
            return False
        if self.is_token_scam(qoute, token_mint):
            return False
        try:
            mint_info = self.get_mint_account_info(token_mint)

            #  Check Mint Authority (Prevents Rug Pulls)
            mint_authority = mint_info.get("mint_authority", None)
            if mint_authority:
                self.logger.warning(
                    f"🚨 Token {token_mint} still has mint authority ({mint_authority})! HIGH RISK."
                )
                return False

            ## Check Freeze Authority (Prevents Wallet Freezing)
            freeze_authority = mint_info.get("freeze_authority", None)
            if freeze_authority:
                self.logger.warning(
                    f"🚨 Token {token_mint} has freeze authority ({freeze_authority})! Devs can freeze funds. HIGH RISK."
                )
                return False


            if self.rug_check_utility.is_liquidity_unlocked(token_mint):
                    self.logger.warning(
                        f"🚨 Token {token_mint} is mutable, owned by dev, AND liquidity is NOT locked! HIGH RISK."
                    )
                    return False
            else:
                self.logger.info(
                        f"⚠️ Token {token_mint} is mutable & dev-owned, but liquidity is locked. Might be safe."
                    )

            self.logger.info(f"✅ Token {token_mint} Safe to proceed.")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error checking scam tests: {e}")
            return False
    
    def get_largest_accounts(self, token_mint: str):
        """Fetch largest token holders and analyze risk."""
        self.logger.info(f"🔍 Checking token holders for {token_mint} using Helius...")

        # Prepare payload
        self.largest_accounts_payload["id"] = self.id
        self.id += 1
        self.largest_accounts_payload["params"][0] = token_mint

        try:
            self.helius_rate_limiter.wait()
            response_json = self.helius_requests.post(
                endpoint=self.api_key,
                payload=self.largest_accounts_payload,
            )

            self.special_logger.debug(f"🔍 Raw Helius Largest Accounts Response: {response_json}")

            if "result" not in response_json:
                self.logger.warning(f"⚠️ Unexpected Helius response structure: {response_json}")
                return False

            holders = response_json["result"]["value"]
            total_supply = self.get_token_supply(token_mint)

            if total_supply == 0:
                self.logger.error("❌ Failed to fetch token supply. Skipping analysis.")
                return False

            # Sort holders by balance
            sorted_holders = sorted(holders, key=lambda x: float(x["uiAmount"]), reverse=True)
            
            #amount of holders
            if len(sorted_holders) < 20:
                return False

            top_holders = sorted_holders[:10]
            top_holder_percentages = [
                (float(holder["uiAmount"]) / total_supply) * 100 for holder in top_holders
            ]
            # 1. Top holder >30% → risky
            if top_holder_percentages[0] > 30:
                return False

            # 2. Top 5 holders >70% combined → risky
            if sum(top_holder_percentages[:5]) > 70:
                return False

            # 3. Uniform bot-like distribution (>5% each, nearly equal)
            if len(top_holder_percentages) > 1:
                min_pct = min(top_holder_percentages[1:])
                max_pct = max(top_holder_percentages[1:])
                if abs(max_pct - min_pct) < 0.01 and max_pct > 5:
                    return False

            # 4. If dev not top holder (<2%) but someone else has >6% → risky
            if top_holder_percentages[0] < 2 and max(top_holder_percentages[1:]) > 6:
                return False

            self.logger.info("✅ Token Holder Analysis Complete.")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error fetching largest accounts from Helius: {e}")
            return False

    def get_burned_accounts(self, token_mint: str):
        """Fetch largest token holders and analyze risk."""
        self.logger.info(f"🔍 Checking token holders for {token_mint} using Helius...")

        # Prepare payload
        self.largest_accounts_payload["id"] = self.id
        self.id += 1
        self.largest_accounts_payload["params"][0] = token_mint

        try:
            self.helius_rate_limiter.wait()
            response_json = self.helius_requests.post(
                endpoint=self.api_key,
                payload=self.largest_accounts_payload,
            )

            self.special_logger.debug(f"🔍 Raw Helius Largest Accounts Response: {response_json}")

            if "result" not in response_json:
                self.logger.warning(f"⚠️ Unexpected Helius response structure: {response_json}")
                return False

            holders = response_json["result"]["value"]
            burned_accounts = []

            for h in holders:
                addr = h["address"]
                bal = float(h["uiAmount"])

                # Heuristics: detect burns
                if (
                    "dead" in addr.lower() or
                    "burn" in addr.lower() or
                    addr.startswith("111111")
                ):
                    burned_accounts.append({
                        "address": addr,
                        "balance": bal
                    })
            return burned_accounts
        except Exception as e:
            self.logger.error(f"❌ Error fetching burned accounts from Helius: {e}")
            return False

    def get_mint_account_info(self, mint_address: str) -> dict:
        resp = self.client.get_account_info(Pubkey.from_string(mint_address))

        if not resp.value or not resp.value.data:
            return {}

        raw_data = resp.value.data
        if isinstance(raw_data, bytes):  
            decoded = raw_data
        elif isinstance(raw_data, list):  
            decoded = bytes(raw_data)
        elif isinstance(raw_data, str):  
            decoded = base64.b64decode(raw_data)
        else:
            raise ValueError(f"Unexpected account data format: {type(raw_data)}")

        # --- Mint authority ---
        mint_auth_option = struct.unpack_from("<I", decoded, 0)[0]
        mint_authority = None
        if mint_auth_option == 1:
            mint_authority = str(Pubkey(decoded[4:36]))

        # --- Supply ---
        supply = struct.unpack_from("<Q", decoded, 36)[0]

        # --- Decimals & init flag ---
        decimals = decoded[44]
        is_initialized = decoded[45] == 1

        # --- Freeze authority ---
        freeze_auth_option = struct.unpack_from("<I", decoded, 46)[0]
        freeze_authority = None
        if freeze_auth_option == 1:
            freeze_authority = str(Pubkey(decoded[50:82]))

        return {
            "mint_authority": mint_authority,
            "freeze_authority": freeze_authority,
            "supply": supply,
            "decimals": decimals,
            "initialized": is_initialized,
        }

    def get_token_meta_data(self, token_mint: str):
        self.special_logger.info(f"🔍 Fetching metadata for {token_mint} using Helius...")
        self.asset_payload["id"] = self.id
        self.id += 1
        try:
            self.asset_payload["params"]["id"] = token_mint
            self.helius_rate_limiter.wait()
            response_json = self.helius_requests.post(
                endpoint=self.api_key,
                payload=self.asset_payload,
            )

            if "result" not in response_json:
                self.logger.warning(f"⚠️ Unexpected Helius response structure: {response_json}")
                return False

            result = response_json["result"]
            content = result.get("content", {})

            token_name = content.get("metadata", {}).get("name")
            token_image = content.get("links", {}).get("image")
            token_address = result.get("id")

            return {
                "name": token_name,
                "image": token_image,
                "token_address": token_address,
            }
        except Exception as e:
            self.logger.error(f"❌ Error fetching token data: {e}")
            return False
    
    def get_token_accounts_by_owner(self, pool_address: str):
        # Prepare payload
        self.token_account_by_owner["id"] = self.id
        self.id += 1
        self.token_account_by_owner["params"][0] = pool_address
        self.token_account_by_owner["params"][1]["programId"] = str(SPL_TOKEN_PROGRAM_ID)

        try:
            self.helius_rate_limiter.wait()
            response_json = self.helius_requests.post(
                endpoint=self.api_key,
                payload=self.token_account_by_owner,
            )

            self.special_logger.debug(f"🔍 Raw Helius token accounts by owner Response: {response_json}")

            if "result" not in response_json:
                self.logger.warning(f"⚠️ Unexpected Helius response structure: {response_json}")
                return False

            accounts = response_json.get("result", {}).get("value", {}).get("accounts", [])
            reserves = []

            for acc in accounts:
                parsed_info = acc["account"]["data"]["parsed"]["info"]
                ta = parsed_info["tokenAmount"]
                reserves.append({
                    "mint": parsed_info["mint"],
                    "amount": int(ta["amount"]),
                    "decimals": int(ta["decimals"]),
                })

            return reserves
        except Exception as e:
                    self.logger.error(f"❌ Failed to fetch pool reserves: {e}", exc_info=True)
                    return []
    
    def calculate_on_chain_price(self,reserve_token: int,token_decimals: int,reserve_base: int,base_decimals: int,base_symbol: str,sol_price: float) -> float:
            """Compute token price in USD from pool reserves."""
            token_amount = reserve_token / (10 ** token_decimals)
            base_amount = reserve_base / (10 ** base_decimals)

            if token_amount == 0:
                return 0.0

            price_in_base = base_amount / token_amount

            if base_symbol == "SOL":
                return price_in_base * sol_price
            elif base_symbol in {"USDC", "USDT"}:
                return price_in_base
            else:
                return 0.0

    def get_token_price_onchain(self, token_mint: str, pool_address: str) -> float:
        """Get USD price for a token using pool reserves and base token info."""
        try:
            reserves = self.get_token_accounts_by_owner(pool_address)
            if len(reserves) < 2:
                self.logger.warning(f"⚠️ Pool {pool_address} has insufficient reserves")
                return 0.0

            token_reserve = next(r for r in reserves if r["mint"] == token_mint)
            base_reserve = next(r for r in reserves if r["mint"] != token_mint)

            base_info = KNOWN_BASES.get(base_reserve["mint"])
            if not base_info:
                self.logger.warning(f"⚠️ Unknown base mint {base_reserve['mint']} in pool {pool_address}")
                return 0.0

            return self.calculate_on_chain_price(
                reserve_token=token_reserve["amount"],
                token_decimals=token_reserve["decimals"],
                reserve_base=base_reserve["amount"],
                base_decimals=base_reserve["decimals"],
                base_symbol=base_info["symbol"],
                sol_price=self.get_sol_price()
            )

        except Exception as e:
            self.logger.error(f"❌ Failed to fetch on-chain price for {token_mint}: {e}", exc_info=True)
            return 0.0

    def get_current_price_on_chain(self, token_mint: str) -> float:
        """Lookup stored pool for a token and return its USD price."""
        pool_entry = self.token_pools.get(token_mint)
        if not pool_entry:
            self.logger.warning(f"⚠️ No pool stored for {token_mint}, cannot fetch price.")
            return 0.0

        pool_address = pool_entry["pool"] if isinstance(pool_entry, dict) else pool_entry
        return self.get_token_price_onchain(token_mint, pool_address)
    
    def store_pool_mapping(self, token_mint: str, transaction: dict):
        try:
            logs = transaction.get("meta", {}).get("logMessages", [])
            post_balances = transaction.get("meta", {}).get("postTokenBalances", [])
            keys = transaction.get("transaction", {}).get("message", {}).get("accountKeys", [])

            pool_address, dex = None, None


            pool_address = self.detect_pool_pda(post_balances, token_mint)

            # decide dex type by program ID present
            if PUMPFUN_PROGRAM_ID in keys:
                dex = "pumpfun"
            elif RAYDIUM_PROGRAM_ID in keys:
                dex = "raydium"

            if pool_address:
                prev_entry = self.token_pools.get(token_mint)
                self.token_pools[token_mint] = {"pool": pool_address, "dex": dex}

                if prev_entry and prev_entry["pool"] != pool_address:
                    self.logger.info(
                        f"🔄 Token {token_mint} migrated pool "
                        f"{prev_entry['pool']} ({prev_entry['dex']}) → {pool_address} ({dex})"
                    )
                    migration_flag = "MIGRATED"
                else:
                    self.logger.info(f"💾 Stored pool {pool_address} ({dex}) for {token_mint}")
                    migration_flag = "NEW"

                # Save/update CSV with migration info
                self.excel_utility.save_to_csv(
                    self.excel_utility.BACKTEST_DIR,
                    "Pair_keys.csv",
                    {
                        "Token Mint": [token_mint],
                        "pair_key": [pool_address],
                        "pool_dex": [dex],
                        "status": [migration_flag],
                    },
                )
            else:
                self.logger.warning(f"⚠️ No pool detected for {token_mint}")

        except Exception as e:
            self.logger.warning(f"⚠️ Failed to store pool for {token_mint}: {e}")

    def detect_pool_pda(self, post_token_balances: list[dict], token_mint: str) -> str | None:

        WSOL = "So11111111111111111111111111111111111111112"
        candidates = []

        for bal in post_token_balances:
            mint = bal.get("mint")
            owner = bal.get("owner")
            ui_amount = bal.get("uiTokenAmount", {}).get("uiAmount", 0)

            if not mint or not owner:
                continue

            candidates.append((owner, mint, ui_amount))

        # Group balances by owner
        owner_balances = {}
        for owner, mint, amount in candidates:
            if owner not in owner_balances:
                owner_balances[owner] = {}
            owner_balances[owner][mint] = amount

        # Find owners that have both WSOL + token
        valid_pools = []
        for owner, balances in owner_balances.items():
            if WSOL in balances and token_mint in balances:
                total_liquidity = balances[WSOL] + balances[token_mint]
                valid_pools.append((owner, total_liquidity))

        if not valid_pools:
            return None

        # ✅ Return the owner with the largest combined WSOL+token balance
        self.logger.debug(f"token owners are {valid_pools}")
        best_owner, _ = max(valid_pools, key=lambda x: x[1])
        return best_owner

    def _update_entry_price_with_balance(self, output_mint: str, usd_amount: float, date_str: str, data: dict):
        MAX_RETRIES = 15
        WAIT_TIME = 2
        token_received = 0

        for attempt in range(MAX_RETRIES):
            time.sleep(WAIT_TIME)
            balances = self.get_account_balances()
            token_info = next((b for b in balances if b['token_mint'] == output_mint), None)
            if token_info and token_info['balance'] > 0:
                token_received = token_info['balance']
                self.logger.info(f"✅ Token received after buy: {token_received}")
                break
            self.logger.warning(f"🔁 Attempt {attempt + 1}: Token not received yet...")

        if token_received > 0:
            real_entry_price = usd_amount / token_received
        else:
            return
        # Update files with true entry price
        data.update({
            "Real_Entry_Price": [real_entry_price],
            "Entry_USD": [real_entry_price],
            "Token_Received": [token_received],
        })

        self.excel_utility.save_to_csv(self.excel_utility.OPEN_POISTIONS, f"bought_tokens_{date_str}.csv", data)
        self.excel_utility.save_to_csv(self.excel_utility.OPEN_POISTIONS, f"open_positions_{date_str}.csv", data)
        self.excel_utility.save_to_csv(self.excel_utility.NOTIFICATIONS, f"discord_{date_str}.csv", data)

        self.logger.info(f"📊 Entry price updated for {output_mint}: {real_entry_price:.8f} USD")

    def get_transaction_data(self, signature: str) -> str | None:
        try:
            self.helius_rate_limiter.wait()
            self.transaction_payload["id"] = self.id
            self.transaction_payload["params"][0] = signature
            self.id += 1
            response = self.helius_requests.post(
                endpoint=self.api_key, payload=self.transaction_payload
            )
            return response
        except Exception as e:
            self.logger.error(f"❌ Error resolving mint for TX {signature}: {e}")
        return None
    
    def get_token_age(self, mint_address: str) -> int | None:
        """Returns age of the mint in seconds. If fails, returns None."""
        try:
            self.helius_rate_limiter.wait()
            self.signature_for_adress["id"] = self.id
            self.id += 1
            self.signature_for_adress["params"][0] = mint_address
            response = self.helius_requests.post(
                endpoint=self.api_key,
                payload=self.signature_for_adress
            )

            if "result" in response and response["result"]:
                first_tx = response["result"][0]
                if "blockTime" in first_tx and first_tx["blockTime"]:
                    return int(time.time()) - int(first_tx["blockTime"])
        except Exception as e:
            self.logger.error(f"❌ Error fetching token age: {e}")
        return None
    
    def get_recent_transactions_signatures_for_token(self, token_mint: str,until=None,before=None) -> list[str]:
        try:     
            self.helius_rate_limiter.wait()         
            self.signature_for_adress["id"] = self.id
            self.id += 1
            self.signature_for_adress["params"][0] = token_mint
            if before:
                self.signature_for_adress["params"][1]["before"] = before  
            if until:
                self.signature_for_adress["params"][1]["until"] = until
            response = self.helius_requests.post(
                endpoint=self.api_key,
                payload=self.signature_for_adress
            )

            txs = response.get("result", [])
            self.logger.debug(f"pulled transactions:{txs}")
            return [tx.get("signature") for tx in txs if "signature" in tx]
        except Exception as e:
            self.logger.error(f"❌ Failed to fetch recent TXs for token {token_mint}: {e}")
            return []  
    
    def parse_helius_swap_volume(self, signatures: list[str]) -> dict:
        volumes = {}

        def fetch_batch(batch):
            try:
                self.helius_rate_limiter.wait()
                payload = {"transactions": batch}
                return self.helius_enhanced.post(endpoint=self.api_key, payload=payload)
            except Exception as e:
                self.logger.error(f"❌ Error fetching batch: {e}")
                return []

        self.logger.info(f"🔍 Extracting volume for {len(signatures)} signatures...")

        try:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(fetch_batch, signatures[i:i+100])
                    for i in range(0, len(signatures), 100)
                ]

                for f in as_completed(futures):
                    txs = f.result()
                    for tx in txs:
                        swap = tx.get("events", {}).get("swap")
                        if swap:
                            token_inputs = swap.get("tokenInputs", [])
                            token_outputs = swap.get("tokenOutputs", [])

                            for native_side, label in [("nativeInput", "buy"), ("nativeOutput", "sell")]:
                                native = swap.get(native_side)
                                if native:
                                    lamports = int(native.get("amount", 0))
                                    sol_amount = lamports / 1e9
                                    usd_value = sol_amount * self.get_sol_price()
                                    self._accumulate(volumes, "So11111111111111111111111111111111111111112", label, usd_value)

                        else:
                            token_inputs = tx.get("tokenTransfers", [])
                            token_outputs = [] 
                            for nt in tx.get("nativeTransfers", []):
                                lamports = int(nt.get("amount", 0))
                                if lamports:
                                    sol_amount = lamports / 1e9
                                    usd_value = sol_amount * self.get_sol_price()
                                    self._accumulate(volumes, "So11111111111111111111111111111111111111112", "sell", usd_value)
                        for t in token_inputs + token_outputs:
                            mint = t.get("mint")
                            raw_amt = t.get("rawTokenAmount", {})
                            decimals = raw_amt.get("decimals") or t.get("decimals", 9)
                            token_amt = raw_amt.get("tokenAmount") or t.get("tokenAmount", 0)
                            amount = float(token_amt) / (10 ** decimals)

                            base_info = KNOWN_BASES.get(mint)
                            if base_info and base_info["symbol"] in {"USDC", "USDT"}:
                                usd_value = amount
                            elif base_info and base_info["symbol"] == "SOL":
                                usd_value = amount * self.get_sol_price()
                            else:
                                usd_price = self.get_current_price_on_chain(mint)
                                usd_value = usd_price * amount if usd_price else 0.0

                            buy, sell = (usd_value, 0.0) if t in token_inputs else (0.0, usd_value)

                            if mint not in volumes:
                                volumes[mint] = {"buy_usd": 0.0, "sell_usd": 0.0}
                            volumes[mint]["buy_usd"] += buy
                            volumes[mint]["sell_usd"] += sell
                            volumes[mint]["total_usd"] = volumes[mint]["buy_usd"] + volumes[mint]["sell_usd"]

        except Exception as e:
            self.logger.error(f"❌ Error extracting volume: {e}")
            return {}

        total_usd = sum(v["total_usd"] for v in volumes.values())
        self.logger.info(f"✅ Finished volume extraction — {len(volumes)} tokens, total volume ${total_usd:,.2f}")
        return volumes

    def _accumulate(self, volumes, mint, label, usd_value):
        if mint not in volumes:
            volumes[mint] = {"buy_usd": 0.0, "sell_usd": 0.0}
        volumes[mint][f"{label}_usd"] += usd_value
        volumes[mint]["total_usd"] = volumes[mint]["buy_usd"] + volumes[mint]["sell_usd"]

    def verify_signature(self, signature: str, data: dict = None, date_str: str = None, token: str = None, action: str = "BUY") -> bool:
        max_retries = 3
        delay = 3

        for attempt in range(max_retries):
            try:
                response = self.get_transaction_data(signature)
                result = response.get("result")
                if result:
                    err = result.get("meta", {}).get("err", None)
                    if err is None:
                        self.logger.info(f"✅ {action} CONFIRMED for {token or signature}")
                        if data and date_str:
                            data["type"] = [action]
                            self.excel_utility.save_to_csv(self.excel_utility.OPEN_POISTIONS, f"open_positions_{date_str}.csv", data)
                            self.excel_utility.save_to_csv(self.excel_utility.NOTIFICATIONS, f"discord_{date_str}.csv", data)
                        return True
                    else:
                        self.logger.warning(f"❌ {action} FAILED for {token or signature}, err={err}")
                        if data and date_str:
                            data["type"] = [f"FAILED_{action}"]
                            self.excel_utility.save_to_csv(self.excel_utility.OPEN_POISTIONS, f"open_positions_{date_str}.csv", data)
                            self.excel_utility.save_to_csv(self.excel_utility.NOTIFICATIONS, f"discord_{date_str}.csv", data)
                        return False
            except Exception as e:
                self.logger.debug(f"⚠️ Error verifying {signature}: {e}")

            if attempt < max_retries - 1:
                self.logger.info(f"⏳ Waiting {delay}s before retrying verification ({attempt+1}/{max_retries})...")
                time.sleep(delay)

        self.logger.warning(f"❌ {action} {signature} not found after {max_retries*delay}s")
        if data and date_str:
            data["type"] = [f"FAILED_{action}"]
            self.excel_utility.save_to_csv(self.excel_utility.OPEN_POISTIONS, f"open_positions_{date_str}.csv", data)
        return False
