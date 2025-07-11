import os
import re
import json
import asyncio
import aiohttp
import discord
from discord.ext import commands

# -----------------------------
# ENVIRONMENT CONFIGURATION
# -----------------------------
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))

MEXC_API_KEY = "mx0vgl8TX4NFHVkxc1"
MEXC_SECRET_KEY = "0cc08527b18a48b1b83f4eba07935350"

# -----------------------------
# MEXC TRADING CONFIGURATION
# -----------------------------
TRADE_SYMBOL = None  # will be updated from signal
TRADE_AMOUNT_USDT = 200
LEVERAGE = 100

# Example TP Split: 25%, 40%, 25%, 10%
TP_SPLIT = [0.25, 0.4, 0.25, 0.1]

# -----------------------------
# DISCORD BOT SETUP
# -----------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot connected as {bot.user}")

@bot.event
async def on_message(message):
    if message.channel.id != SOURCE_CHANNEL_ID:
        return

    content = message.content.upper()

    # Signal parsing logic
    match = re.search(r"(\w+USDT).*?BUYZONE.*?(\d+\.\d+).*?-.*?(\d+\.\d+).*?STOP.*?(\d+\.\d+).*?LEVERAGE.*?X(\d+).*?TARGETS(.*?)\Z", content, re.DOTALL)
    if not match:
        print("❌ Could not parse message.")
        return

    symbol = match.group(1)
    buy_min = float(match.group(2))
    buy_max = float(match.group(3))
    stop_loss = float(match.group(4))
    leverage = int(match.group(5))
    targets_text = match.group(6).strip()

    target_prices = re.findall(r"\d+\.\d+", targets_text)
    target_prices = [float(p) for p in target_prices[:4]]  # Ignore any 5th or more

    print(f"📈 Parsed Trade Signal: {symbol} at zone {buy_min}-{buy_max}, TP: {target_prices}, SL: {stop_loss}, Lev: x{leverage}")

    await execute_trade(symbol, buy_max, stop_loss, target_prices, leverage)

# -----------------------------
# MEXC TRADE EXECUTION
# -----------------------------
async def execute_trade(symbol, entry_price, stop_loss, targets, leverage):
    base_url = "https://contract.mexc.com"
    headers = {
        "Content-Type": "application/json",
        "ApiKey": MEXC_API_KEY
    }

    # Build signature (MEXC-specific, simplified for demo)
    async with aiohttp.ClientSession() as session:
        # 1. Set leverage
        lev_payload = {
            "symbol": symbol,
            "leverage": leverage,
            "positionOpenType": 1
        }
        async with session.post(base_url + "/api/v1/private/position/change-leverage", json=lev_payload, headers=headers) as resp:
            print("Leverage response:", await resp.text())

        # 2. Place market order (long)
        trade_payload = {
            "symbol": symbol,
            "price": 0,  # market order
            "vol": TRADE_AMOUNT_USDT,
            "leverage": leverage,
            "side": 1,  # 1 = Buy Long
            "type": 1,  # 1 = Market
            "openType": 1,
            "positionId": 0,
            "externalOid": os.urandom(6).hex(),
            "stopLossPrice": stop_loss
        }

        async with session.post(base_url + "/api/v1/private/order/submit", json=trade_payload, headers=headers) as resp:
            order_response = await resp.text()
            print("📤 Trade response:", order_response)

        # 3. (Optional) Place limit orders for TPs at % allocation
        for i, tp_price in enumerate(targets):
            tp_vol = round(TRADE_AMOUNT_USDT * TP_SPLIT[i], 2)
            tp_payload = {
                "symbol": symbol,
                "price": tp_price,
                "vol": tp_vol,
                "leverage": leverage,
                "side": 2,  # 2 = Sell to Close
                "type": 1,  # Market
                "openType": 1,
                "positionId": 0,
                "externalOid": os.urandom(6).hex()
            }
            async with session.post(base_url + "/api/v1/private/order/submit", json=tp_payload, headers=headers) as tp_resp:
                print(f"🎯 TP{i+1} response:", await tp_resp.text())

# -----------------------------
# RUN BOT
# -----------------------------
bot.run(DISCORD_BOT_TOKEN)
