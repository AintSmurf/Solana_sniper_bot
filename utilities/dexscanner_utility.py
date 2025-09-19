from config.third_parties import DEXSCANNER
from utilities.requests_utility import RequestsUtility
from helpers.logging_manager import LoggingHandler

# set up logger
logger = LoggingHandler.get_logger()


class DexscannerUtility:
    def __init__(self):
        base_url = DEXSCANNER["BASE_URL"]
        self.data = DEXSCANNER["TOKEN_DATA"]
        self.pool = DEXSCANNER["TOKEN_POOL"]
        self.new_pairs = DEXSCANNER["NEW_TOKENS"]
        self.requests_utility = RequestsUtility(base_url)
        logger.info("initialized Dexscreener class.")

    def print_solana_tokens(self):
        logger.info("Retriving token and token address ....")
        data = self.requests_utility.get(self.new_pairs)
        solana_tokens = [token for token in data if token["chainId"] == "solana"]

        for token in solana_tokens:
            print(f"Token: {token.get('description', 'No description')}")
            print(f"Address: {token['tokenAddress']}")
            print(f"DEX Link: {token['url']}\n")

    def get_token_data(self, chain_id, pair_id):
        logger.info("Retriving token liquidity and marketcap ...")
        url = self.data + f"/{chain_id}/{pair_id}"
        info = self.requests_utility.get(url)
        print(info)

    def get_token_pair_address(self, chain_id: str, token_address: str, dex_id: str = None) -> dict:
        """
        Retrieve token pair address from dexscreener.
        If dex_id is provided, return only that DEX entry (e.g. pumpswap, raydium, meteora).
        Otherwise return the first available.
        """
        logger.info(f"Retrieving token pair address for {token_address} on {chain_id} (dex={dex_id})...")
        url = f"{self.pool}/{chain_id}/{token_address}"
        info = self.requests_utility.get(url)

        if not info:
            logger.warning(f"⚠️ No pair info found for {token_address}")
            return {}

        chosen = None
        if dex_id:
            chosen = next((entry for entry in info if entry.get("dexId") == dex_id), None)

        if not chosen:  # fallback to first entry
            chosen = info[0]

        return {
            "base": [chosen["baseToken"]["address"]],
            "quoteToken": [chosen["quoteToken"]["address"]],
            "pool_address": [chosen["pairAddress"]],
            "dex_id": chosen["dexId"],
        }
