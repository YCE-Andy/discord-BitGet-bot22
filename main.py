import os
import re
import json
import time
import hmac
import hashlib
import asyncio
import aiohttp
import discord
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 200))
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

client = discord.Client(intents=discord.Intents.all())

API_URL = "https://api.bitget.com"
HEADERS = {
    "Content-Type": "application/json",
    "ACCESS-KEY": BITGET_API_KEY,
    "ACCESS-PASSPHRASE": BITGET_PASSPHRASE
}

# === BITGET SIGNING ===
def bitget_signature(timestamp, method, request_path, body):
    message = f'{timestamp}{method}{request_path}{body}'
    signature = hmac.new(BITGET_SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()
    return signature

async def place_market_order(symbol, side, size):
    timestamp = str(int(time.time() * 1000))
    path = "/api/v2/mix/order/place-order"
    url = API_URL + path
    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": str(size),
        "price": "",
        "side": side,
        "orderType": "market",
        "marketType": "futures",
        "productType": "umcbl",
        "marginMode": "isolated"
    }
    json_body = json.dumps(body)
    signature = bitget_signature(timestamp, "POST", path, json_body)
    HEADERS.update({
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-SIGN": signature
    })
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=HEADERS, data=json_body) as resp:
            response = await resp.json()
            return response

@client.event
async def on_ready():
    print(f'✅ Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.channel.id != SOURCE_CHANNEL_ID or message.author == client.user:
        return

    content = message.content.upper()
    print("🟨 Signal received")

    symbol_match = re.search(r"(\w+USDT)", content)
    buyzone_match = re.search(r"BUYZONE\s+(\d+\.?\d*)\s*-\s*(\d+\.?\d*)", content)
    targets_match = re.findall(r"TARGETS[\s\n]+((?:\d+\.?\d*\s*)+)", content)
    stop_match = re.search(r"STOP\s+(\d+\.?\d*)", content)
    leverage_match = re.search(r"LEVERAGE\s*X?(\d+)", content)

    if not (symbol_match and buyzone_match and targets_match and stop_match):
        print("❌ Error: Could not parse all required signal fields.")
        return

    raw_symbol = symbol_match.group(1)
    buyzone_low = float(buyzone_match.group(1))
    buyzone_high = float(buyzone_match.group(2))
    stop_price = float(stop_match.group(1))
    leverage = int(leverage_match.group(1)) if leverage_match else 5

    targets = [float(t) for t in re.findall(r"\d+\.?\d*", targets_match[0])][:5]
    tp_percents = [0.5, 0.2, 0.15, 0.1, 0.05]

    symbol = raw_symbol
    size = round(TRADE_AMOUNT / ((buyzone_low + buyzone_high) / 2), 3)

    # Entry
    side = "buy" if "SHORT" not in content else "sell"
    order = await place_market_order(symbol, side, size)

    if order.get("code") == "00000":
        print(f"✅ Bitget Order Placed: {symbol} x{leverage} [{side.upper()}]")
    else:
        print(f"❌ Trade Failed: {order}")
        return

    # TP/SL placeholders (until we rewrite this with working Bitget V2 plan orders)
    for i, tp in enumerate(targets):
        print(f"📈 TP @{tp}: ❌ Plan not placed (awaiting working V2 logic)")

    print(f"🛑 SL @{stop_price}: ❌ Plan not placed (awaiting working V2 logic)")

client.run(DISCORD_BOT_TOKEN)
