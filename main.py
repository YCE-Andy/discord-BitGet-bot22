import discord
import os
import asyncio

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# Load environment variables safely
try:
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID", "0").strip())
    TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", "0").strip())
except Exception as e:
    print(f"[ERROR] Failed to load environment variables: {e}")
    exit(1)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}! Bot is ready.')

@client.event
async def on_message(message):
    if message.channel.id == SOURCE_CHANNEL_ID and not message.author.bot:
        target_channel = client.get_channel(TARGET_CHANNEL_ID)
        if target_channel:
            await target_channel.send(f"[Relay] {message.content}")

client.run(DISCORD_BOT_TOKEN)
