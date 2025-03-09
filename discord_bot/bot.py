import discord
import asyncio
import os
import pandas as pd
from discord.ext import commands
import logging
from utilities.credentials_utility import CredentialsUtility
from utilities.excel_utility import ExcelUtility
from datetime import datetime
from helpers.logging_manager import LoggingHandler

# Set up logger
logger = LoggingHandler.get_logger()


class Discord_Bot:
    def __init__(self):
        self.credentials_utility = CredentialsUtility()
        self.token = self.credentials_utility.get_discord_token()
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.bot_ready = asyncio.Event()  # ✅ Async event for bot readiness
        self.excel_utility = ExcelUtility()  # ✅ Initialize Excel utility
        self.last_row_counts = {}  # ✅ Track last processed row count per file

        @self.bot.event
        async def on_ready():
            self.bot_ready.set()  # ✅ Mark bot as ready
            logger.info(f"✅ Bot is ready! Logged in as {self.bot.user}")

    async def send_message_to_discord(self, channel_name, content):
        """Send a message to a specific Discord channel."""
        await self.bot_ready.wait()  # ✅ Wait until bot is ready

        channel = discord.utils.get(self.bot.get_all_channels(), name=channel_name)
        if channel:
            await channel.send(content)
        else:
            logger.warning(f"❌ Channel '{channel_name}' not found!")

    async def send_message_from_sniper(
        self, token_mint, token_owner, liquidity, market_cap, choice, dexscreener_link
    ):
        """Send different messages depending on whether it's a Rug Check or Transaction Check."""
        await self.bot_ready.wait()

        if choice == 1:
            message = (
                f"🚨 **Potential Rug Detected!** 🚨\n"
                f"🔹 **Mint Address:** `{token_mint}`\n"
                f"🔹 **Owner:** `{token_owner}`\n"
                f"🔹 **Liquidity:** `{liquidity}`\n"
                f"🔹 **Market Cap:** `{market_cap}`\n"
                f"🔹 **[DexScreener Link]({dexscreener_link})**\n"
                f"⚠️ **Warning: This token failed a security check!**"
            )
        else:
            message = (
                f"🚀 **New Token Passed Transaction Check!** 🚀\n"
                f"🔹 **Mint Address:** `{token_mint}`\n"
                f"🔹 **Owner:** `{token_owner}`\n"
                f"🔹 **Liquidity (Estimated):** `{liquidity}`\n"
                f"🔹 **Market Cap:** `{market_cap}`\n"
                f"🔹 **[DexScreener Link]({dexscreener_link})**\n"
                f"✅ **Not a Honeypot!**"
            )

        await self.send_message_to_discord("solana_tokens", message)

    async def watch_excel_for_updates(self):
        """Watches both the Rug Check and Transactions Check files for new entries."""
        while True:
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            transactions_file = f"transactions_{date_str}.csv"
            rug_check_file = f"rug_check_{date_str}.csv"

            await self.check_and_send_new_entries(
                self.excel_utility.TRANSACTIONS_DIR, transactions_file, 2
            )
            await self.check_and_send_new_entries(
                self.excel_utility.TOKENS_DIR, rug_check_file, 1
            )

            await asyncio.sleep(10)

    async def check_and_send_new_entries(self, folder, filename, message_type):
        """Reads the transactions file, sends new data to Discord, and updates the file."""
        filepath = os.path.join(folder, filename)
        if not os.path.exists(filepath):
            return

        try:
            df = pd.read_csv(filepath)

            last_processed = self.last_row_counts.get(filepath, 0)
            total_rows = len(df)

            if total_rows > last_processed:
                new_rows = df.loc[~df["SentToDiscord"]]  # Filter rows not sent

                for index, row in new_rows.iterrows():
                    token_mint = row["Token Mint"]
                    token_owner = row["Token Owner"]
                    liquidity = row["Liquidity (Estimated)"]
                    market_cap = row["Market Cap"]
                    dexscreener_link = f"https://dexscreener.com/solana/{token_mint}"

                    await self.send_message_from_sniper(
                        token_mint,
                        token_owner,
                        liquidity,
                        market_cap,
                        message_type,
                        dexscreener_link,
                    )

                    df.loc[index, "SentToDiscord"] = True  # Update sent status

                df.to_csv(filepath, index=False)  # Save changes
                logger.info(f"✅ Updated {filename}, marked sent messages.")
                self.last_row_counts[filepath] = total_rows

        except Exception as e:
            logger.error(f"❌ Error reading/updating {filename}: {e}")

    async def run(self):
        """Runs the bot and starts watching Excel files for updates."""
        asyncio.create_task(self.watch_excel_for_updates())
        await self.bot.start(self.token["DISCORD_TOKEN"])
