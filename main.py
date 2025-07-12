# ✅ MEXC Futures Auto-Trader Bot with Discord Alerts (No ccxt, Direct API)

import discord
import asyncio
import aiohttp
import hmac
import hashlib
import time
import os

# 🔐 Load from environment vars (Railway recommended)
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))  # Must be int
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
API_BASE = "https://contract.mexc.com"

# ⚙️ Configure trade amount
USDT_PER_TRADE = 20  # Small amount for test/live safety

intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

# 🔐 MEXC Signature Generator
def sign(params):
    sorted_params = sorted(params.items())
    query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
    signature = hmac.new(MEXC_SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    return signature

# 🛒 Place Futures Order
def build_order(symbol, price, vol, leverage, side):
    return {
        "symbol": symbol,
        "price": price,
        "vol": vol,
        "leverage": leverage,
        "side": 1 if side == "buy" else 2,
        "type": 1,  # Market order
        "open_type": 1,
        "position_id": 0,
        "external_oid": str(int(time.time() * 1000)),
        "stop_loss_price": 0,
        "take_profit_price": 0,
        "position_mode": 1,
        "reduce_only": False
    }

async def place_futures_order(symbol, price, usdt_amount, leverage, side):
    timestamp = int(time.time() * 1000)
    qty = round(usdt_amount / price, 3)  # ⚠️ Ensure correct precision manually
    order = build_order(symbol, price, qty, leverage, side)
    order["api_key"] = MEXC_API_KEY
    order["req_time"] = timestamp
    order["sign"] = sign(order)

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE}/api/v1/private/order/submit", data=order) as resp:
            return await resp.json()

# 🔍 Parse Signal Message
def parse_signal(content):
    lines = content.strip().split("\n")
    signal = {}
    for line in lines:
        l = line.strip().upper()
        if l.startswith("BUYZONE"):
            prices = [float(x.strip()) for x in l.replace("BUYZONE", "").split("-")]
            signal["buyzone"] = sum(prices) / len(prices)
        elif l.startswith("STOP"):
            signal["stop"] = float(l.replace("STOP", "").strip())
        elif l.startswith("LEVERAGE"):
            signal["leverage"] = int(l.replace("LEVERAGE", "").replace("X", "").strip())
        elif l.endswith("USDT"):
            symbol = l.replace("USDT", "_USDT")
            signal["symbol"] = symbol
    return signal if "symbol" in signal and "buyzone" in signal else None

@client.event
async def on_ready():
    print(f"[READY] Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID or message.author == client.user:
        return

    signal = parse_signal(message.content)
    if not signal:
        return

    try:
        response = await place_futures_order(
            symbol=signal["symbol"],
            price=signal["buyzone"],
            usdt_amount=USDT_PER_TRADE,
            leverage=signal.get("leverage", 5),
            side="buy"
        )

        if response.get("success"):
            await message.channel.send(f"✅ Trade executed: {signal['symbol']} @ {signal['buyzone']} x{signal['leverage']}")
        else:
            await message.channel.send(f"❌ Trade failed: {response.get('message', 'Unknown error')}")

    except Exception as e:
        await message.channel.send(f"⚠️ Error placing trade: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
