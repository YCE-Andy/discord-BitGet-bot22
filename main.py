import os
import re
import hmac
import time
import json
import hashlib
import aiohttp
import discord
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")

API_BASE = "https://contract.mexc.com"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def parse_signal(content):
    content = content.upper()
    match = re.search(r"^([A-Z]+USDT)", content)
    base = match.group(1).replace("USDT", "") if match else None
    if not base:
        return None

    symbol = f"{base}_USDT"
    side = 'BUY' if 'BUY' in content else 'SELL'
    leverage = int(re.search(r"LEVERAGE\s*[Xx]?(\d+)", content).group(1)) if re.search(r"LEVERAGE\s*[Xx]?(\d+)", content) else 5
    price_match = re.search(r"BUYZONE\s*([\d.]+)\s*-\s*([\d.]+)", content)
    price = float(price_match.group(1)) if price_match else 0
    return {
        "symbol": symbol,
        "side": side,
        "price": price,
        "leverage": leverage
    }

def sign(params):
    query = urlencode(params)
    signature = hmac.new(MEXC_SECRET_KEY.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

async def place_futures_order(symbol, side, quantity, leverage):
    url = f"{API_BASE}/api/v1/private/order/submit"
    timestamp = int(time.time() * 1000)

    order_params = {
        "api_key": MEXC_API_KEY,
        "req_time": timestamp,
        "symbol": symbol,
        "price": 0,
        "vol": quantity,
        "leverage": leverage,
        "side": 1 if side == "BUY" else 2,
        "type": 1,  # market order
        "open_type": 1,
        "position_id": 0,
        "external_oid": str(int(time.time() * 1000)),
        "stop_loss_price": 0,
        "take_profit_price": 0,
        "position_mode": 1
    }
    order_params["sign"] = sign(order_params)

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=order_params) as response:
            return await response.json()

@client.event
async def on_ready():
    print(f"[READY] Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user or message.channel.id != RELAY_CHANNEL_ID:
        return

    print(f"[MESSAGE] {message.content.strip()}\nFrom: {message.author} | Channel: {message.channel.id}")
    signal = parse_signal(message.content)
    if not signal:
        await message.channel.send("[ERROR] Could not parse the trading signal.")
        return

    try:
        symbol = signal["symbol"]
        side = signal["side"]
        leverage = signal["leverage"]
        quantity = 1  # very small default for testing

        result = await place_futures_order(symbol, side, quantity, leverage)

        if result.get("success"):
            await message.channel.send(f"[SUCCESS] Trade executed: {side} {quantity} {symbol} x{leverage}")
        else:
            await message.channel.send(f"[ERROR] Trade failed: {json.dumps(result)}")

    except Exception as e:
        await message.channel.send(f"[EXCEPTION] Trade error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
