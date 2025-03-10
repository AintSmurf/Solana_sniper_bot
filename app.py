import asyncio
from discord_bot.bot import Discord_Bot
from connectors.helius_connector import HeliusConnector
from helpers.logging_manager import LoggingHandler
from helpers.solana_manager import SolanaHandler
from utilities.rug_check_utility import RugCheckUtility
import threading
import time
import base64

# set up logger
logger = LoggingHandler.get_logger()


def start_discord_bot():
    ds = Discord_Bot()
    asyncio.run(ds.run())


def main():
    helius_connector = HeliusConnector()

    ws_thread = threading.Thread(target=helius_connector.start_ws, daemon=True)
    ws_thread.start()
    logger.info("🚀 WebSocket Started")

    fetcher_thread = threading.Thread(
        target=helius_connector.run_transaction_fetcher, daemon=True
    )
    fetcher_thread.start()
    logger.info("✅ Transaction fetcher started")

    discord_thread = threading.Thread(target=start_discord_bot, daemon=True)
    discord_thread.start()
    logger.info("✅ Discord bot (with Excel watcher) started in a separate thread")

    while True:
        time.sleep(1)


def test():
    # pass
    # helius_connector = HeliusConnector()
    # rug = RugCheckUtility()
    # print(rug.is_liquidity_unlocked("8QhSMvYfXome11VgxFMD75hNbGQXW5QTnjA8khENkY2c"))
    solana_manager = SolanaHandler()
    # print(
    #     solana_manager.get_raydium_marketcap(
    #         "53pKGZ9JAvkpMEmfdhm3epX9bVRjLJaBGjSgHAWipump"
    #     ))

    # print(
    #     helius_connector.get_raydium_liquidity(
    #         "53pKGZ9JAvkpMEmfdhm3epX9bVRjLJaBGjSgHAWipump"
    #     )
    # )
    # print(
    #     helius_connector.get_raydium_marketcap(
    #         "53pKGZ9JAvkpMEmfdhm3epX9bVRjLJaBGjSgHAWipump"
    #     )
    # )

    # rg = RugCheckUtility()
    # print(rg.is_liquidity_unlocked("CCYBBVkocwTk85qT4jbb8k65u2ufYkjoyrdFkUPKGVs6"))
    # sl = SolanaHandler()
    # sl.add_token_account("AvNXHBAk9wSQWeVPzTTYJp5VCpnW73fBdp7ijbyrpump")
    solana_manager.check_scam_functions_helius(
        "5U69kri5SNr8J6cdN6pFnSHnsjKyfeMWW98gASL8pump"
    )
    # amount = solana_manager.get_token_worth_in_usd(
    #     "CRQRS919RU9vhFxHTHZsVnrgfK68H1a1LZ3qkvcepump", 25
    # )
    # quote = solana_manager.get_quote(
    #     "CRQRS919RU9vhFxHTHZsVnrgfK68H1a1LZ3qkvcepump",
    #     "So11111111111111111111111111111111111111112",
    #     amount,
    #     test=True,
    # )
    # print(quote)
    # print(sl.simulate_transaction(txn64))
    # solana_manager.buy(
    #     "So11111111111111111111111111111111111111112",
    #     "8QhSMvYfXome11VgxFMD75hNbGQXW5QTnjA8khENkY2c",
    #     15,
    # )
    # print(solana_manager.get_account_balances())
    # solana_manager.sell(
    #     "8QhSMvYfXome11VgxFMD75hNbGQXW5QTnjA8khENkY2c",
    #     "So11111111111111111111111111111111111111112",
    # )


if __name__ == "__main__":
    main()
