import discord
import asyncio
import os
import pandas as pd
from discord.ext import commands
from utilities.credentials_utility import CredentialsUtility
from utilities.excel_utility import ExcelUtility
from datetime import datetime
from helpers.logging_manager import LoggingHandler
import time

# Set up logger
logger = LoggingHandler.get_logger()


class Discord_Bot:
    def __init__(self):
        self.credentials_utility = CredentialsUtility()
        self.token = None  # Delay token loading

        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.bot_ready = asyncio.Event()
        
        self.excel_utility = None  # Delay ExcelUtility init
        self.last_row_counts = {}

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
        self, token_mint, investment,choice, dexscreener_link
    ):
        """Send different messages depending on whether it's a Rug Check or Transaction Check."""
        await self.bot_ready.wait()

        if choice == 1:
            message = (
                f"🚨 **passed first test - HoneyPut and mint authority** 🚨\n"
                f"🔹 **Mint Address:** `{token_mint}`\n"
                f"🔹 **investment:** `{investment}`\n"
                f"🔹 **DexScreener Link**: <{dexscreener_link}>\n"
                f"⚠️ **Warning: This token didnt pass yet the rest of the tests**"
            )
        else:
            message = (
                f"🚀 **New Token Passed all tests** 🚀\n"
                f"🔹 **Mint Address:** `{token_mint}`\n"
                f"🔹 **investment:** `{investment}`\n"
                f"🔹 **DexScreener Link**: <{dexscreener_link}>\n"
            )

        await self.send_message_to_discord("solana_tokens", message)

    async def watch_excel_for_updates(self):
        while True:
            logger.debug("📊 Checking for new Excel entries...")
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            rug_check_file = f"discord_{date_str}.csv"
            await self.check_and_send_new_entries(
                self.excel_utility.BOUGHT_TOKENS, rug_check_file, 1
            )

            await asyncio.sleep(5)
    
    async def check_and_send_new_entries(self, folder, filename, message_type):
        filepath = os.path.join(folder, filename)
        required_columns = ["Token_bought","SentToDiscord"]

        # Keep trying until file exists and is readable with required columns
        while True:
            if not os.path.exists(filepath):
                logger.debug("📭 Waiting for buy file to be created...")
                await asyncio.sleep(1)
                continue

            try:
                df = pd.read_csv(filepath)

                # Check for required columns
                if not all(col in df.columns for col in required_columns):
                    logger.debug("📄 File exists but missing required columns — waiting...")
                    await asyncio.sleep(1)
                    continue

                break  # file is ready

            except Exception as e:
                logger.debug(f"⏳ File not ready yet ({e}) — retrying...")
                await asyncio.sleep(1)

        # ✅ Now file exists and is valid — proceed safely
        try:
            df["SentToDiscord"] = df["SentToDiscord"].fillna(False).astype(bool)

            last_processed = self.last_row_counts.get(filepath, 0)
            total_rows = len(df)

            if total_rows > last_processed:
                new_rows = df.loc[~df["SentToDiscord"]]

                for index, row in new_rows.iterrows():
                    try:
                        token_mint = row["Token_bought"]
                        investment = row.get("USD", "N/A")
                        dexscreener_link = f"https://dexscreener.com/solana/{token_mint}"

                        await self.send_message_from_sniper(
                            token_mint,
                            investment,
                            message_type,
                            dexscreener_link,
                        )

                        df.loc[index, "SentToDiscord"] = True
                        logger.info(f"✅ token: {token_mint} sent to discord")

                    except Exception as row_error:
                        logger.error(f"⚠️ Error processing row {index}: {row_error}")

                df.to_csv(filepath, index=False)
                logger.info(f"✅ Updated {filename}, marked sent messages.")
                self.last_row_counts[filepath] = total_rows

        except Exception as e:
            logger.error(f"❌ Error processing {filename}: {e}")
    
    async def run(self):
        self.token = self.credentials_utility.get_discord_token() 
        self.excel_utility = ExcelUtility()  
        asyncio.create_task(self.watch_excel_for_updates())
        await self.bot.start(self.token["DISCORD_TOKEN"])

    async def shutdown(self):
        """Gracefully shut down the Discord bot."""
        logger.info("👋 Shutting down Discord bot...")
        await self.bot.close()