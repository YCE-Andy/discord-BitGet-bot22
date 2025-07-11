import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {{bot.user}}")

@bot.event
async def on_message(message):
    if message.channel.id == SOURCE_CHANNEL_ID and not message.author.bot:
        relay_channel = bot.get_channel(RELAY_CHANNEL_ID)
        if relay_channel:
            await relay_channel.send(f"**{message.author.display_name}**: {message.content}")
    await bot.process_commands(message)

bot.run(TOKEN)
