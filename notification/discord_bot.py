import discord
import asyncio
from discord.ext import commands,tasks

class Discord_Bot:
    def __init__(self, token, logger):
        self.token = token
        self.logger = logger

        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.bot_ready = asyncio.Event()

        @self.bot.event
        async def on_ready():
            self.bot_ready.set()
            self.logger.info(f"✅ Discord bot logged in as {self.bot.user}")    
        @self.bot.command(name="hello")
        async def hello(ctx):
            if ctx.channel.name != "general": 
                await ctx.send("⚠️ Commands only work in #general.")
                return
            await ctx.send(f"👋 Hello {ctx.author.display_name}!")

    async def send_message(self, channel_name: str, content: str):
        await self.bot_ready.wait()
        channel = discord.utils.get(self.bot.get_all_channels(), name=channel_name)
        if channel:
            await channel.send(content)
        else:
            self.logger.warning(f"❌ Discord channel '{channel_name}' not found")

    async def run(self):
        await self.bot.start(self.token)

    async def shutdown(self):
        await self.bot.close()
    
    @tasks.loop(hours=24)
    async def daily_cleanup(self):
        await self.bot_ready.wait()
        channel = discord.utils.get(self.bot.get_all_channels(), name="live")
        if channel:
            deleted = await channel.purge(limit=1000)
            self.logger.info(f"🧹 Cleared {len(deleted)} messages from #live")
        else:
            self.logger.warning("❌ #live channel not found for cleanup")