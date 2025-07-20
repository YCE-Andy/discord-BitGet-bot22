.py file

import os
import time
import asyncio
import requests
import discord
from discord.ext import tasks, commands
from datetime import datetime, timedelta
from mexc_api import fetch_mexc_futures_symbols, find_trade_setups

# ENV Variables
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Discord setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send("✅ MEXC Bot is live and scanning for trades!")
    scan_for_trades.start()

# Telegram helper
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    try:
        response = requests.post(url, json=payload)
        return response.ok
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

# 🧠 Trade scanner
@tasks.loop(minutes=15)
async def scan_for_trades():
    try:
        print(f"🔍 Scanning for trades at {datetime.utcnow().isoformat()}...")

        symbols = fetch_mexc_futures_symbols()
        setups = find_trade_setups(symbols)

        if not setups:
            msg = "📭 No strong trade setups found this scan."
            print(msg)
            await bot.get_channel(DISCORD_CHANNEL_ID).send(msg)
            send_telegram_message(msg)
            return

        top_setups = sorted(setups, key=lambda x: abs(x['potential']), reverse=True)[:10]
        for setup in top_setups:
            message = (
                f"{setup['symbol']}\n\n"
                f"{'BUYZONE' if setup['side'] == 'long' else 'SELLZONE'} {setup['entry_low']} - {setup['entry_high']}\n\n"
                f"TARGETS\n" +
                "\n".join([f"{t}" for t in setup['targets']]) +
                f"\n\nSTOP {setup['stop']}\n\nLeverage x{setup['leverage']}"
            )
            await bot.get_channel(DISCORD_CHANNEL_ID).send(message)
            send_telegram_message(message)

    except Exception as e:
        print(f"❌ Error in scan: {e}")
        await bot.get_channel(DISCORD_CHANNEL_ID).send(f"❌ Error in scan: {e}")
        send_telegram_message(f"❌ Error in scan: {e}")

# Start bot
bot.run(DISCORD_TOKEN)
