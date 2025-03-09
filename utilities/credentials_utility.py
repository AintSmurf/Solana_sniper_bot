import os
from helpers.logging_manager import LoggingHandler


# set up logger
logger = LoggingHandler.get_logger()


class CredentialsUtility:
    def __init__(self) -> None:
        self.api_key = ""
        self.secret_key = ""

    def get_helius_api_key(self):
        logger.info("retriving helius api key ...")
        self.api_key = os.environ["API_KEY"]
        return {"API_KEY": self.api_key}

    def get_solana_private_wallet_key(self):
        logger.info("retriving solana private key ...")
        self.api_key = os.environ["SOLANA_PRIVATE_KEY"]
        return {"SOLANA_PRIVATE_KEY": self.api_key}

    def get_discord_token(self):
        logger.info("retriving discord token ...")
        self.api_key = os.environ["DISCORD_TOKEN"]
        return {"DISCORD_TOKEN": self.api_key}
