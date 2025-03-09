from requests import get
from config.urls import DEXSCANNER
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

    def get_token_pair_address(self, chain_id, tokenAddress):
        logger.info("Retriving token pair address ...")
        url = self.pool + f"/{chain_id}/{tokenAddress}"
        info = self.requests_utility.get(url)
        print(info)
