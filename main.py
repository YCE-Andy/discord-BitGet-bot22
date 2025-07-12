import os
import re
import json
import time
import hmac
import hashlib
import requests
import discord
import asyncio
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")

API_BASE = "https://contract.mexc.com"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# --- Fetch available symbols from MEXC ---
def get_symbol_info():
    url = f"{API_BASE}/api/v1/contract/detail"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {item["symbol"]: item for item in data["data"]}
        else:
            return None
    except Exception as e:
        print(f"[ERROR] Failed to fetch symbols from MEXC: {e}")
        return None

# --- Place futures order using MEXC Futures API ---
def place_futures_order(symbol, side, quantity, leverage):
    endpoint = "/api/v1/private/order/submit"
    url = API_BASE + endpoint

    timestamp = str(int(time.time() * 1000))
    order_type = 1  # Market order
    open_type = 1   # Cross margin
    position_type = 1 if side == "buy" else 2

    order_params = {
        "api_key": MEXC_API_KEY,
        "req_time": timestamp,
        "symbol": symbol,
        "price": 0,
        "vol": quantity,
        "leverage": leverage,
        "side": 1 if side == "buy" else 2,
        "type": order_type,
        "open_type": open_type,
        "position_type": position_type,
    }

    query = '&'.join([f"{key}={order_params[key]}" for key in sorted(order_params)])
    signature = hmac.new(MEXC_SECRET_KEY.encode(), query.encode(), hashlib.sha256).hexdigest()
    order_params["sign"] = signature

    response = requests.post(url, data=order_params)
    return response.json()

# --- Parse signal and execute trade ---
@client.event
async def on_message(message):
    if message.channel.id != RELAY_CHANNEL_ID or message.author == client.user:
        return

    content = message.content
    match = re.search(r"([A-Z]+USDT)\s+BUYZONE\s+([\d.]+)\s*-\s*([\d.]+).*?TARGETS\s+(.*?)\s+STOP\s+([\d.]+).*?LEVERAGE\s+x(\d+)", content, re.DOTALL)
    if not match:
        return

    base_symbol, buy_low, buy_high, targets_raw, stop, leverage = match.groups()
    leverage = int(leverage)
    buy_price = (float(buy_low) + float(buy_high)) / 2
    usdt_amount = 200
    qty = Decimal(usdt_amount / buy_price).quantize(Decimal("1.0000"), rounding=ROUND_DOWN)

    # Fetch symbol info with retry
    all_symbols = get_symbol_info()
    if not all_symbols:
        await message.channel.send("[ERROR] Failed to fetch trading pairs from MEXC. Try again later.")
        return

    # Match symbol
    futures_symbol = f"{base_symbol}_USDT"
    if futures_symbol not in all_symbols:
        await message.channel.send(f"[ERROR] Market {futures_symbol} not found on MEXC.")
        return

    await message.channel.send(f"🚀 Placing market order: BUY {qty} {futures_symbol} with x{leverage} leverage")
    try:
        result = place_futures_order(futures_symbol, "buy", str(qty), leverage)
        if result.get("success"):
            await message.channel.send(f"✅ Trade executed successfully! Order ID: {result['data']['order_id']}")
        else:
            await message.channel.send(f"[ERROR] Trade failed: {result.get('message') or result}")
    except Exception as e:
        await message.channel.send(f"[ERROR] Exception during trade: {str(e)}")

@client.event
async def on_ready():
    print(f"[READY] Logged in as {client.user}")

client.run(TOKEN)
