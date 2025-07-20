import os
import time
import json
import hmac
import base64
import hashlib
import requests
import discord
import asyncio
from decimal import Decimal, ROUND_DOWN

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

BITGET_API_URL = "https://api.bitget.com"
TRADE_AMOUNT_PERCENT = 0.2
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))

# Discord client
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

symbol_precision_map = {}

# Helper to generate Bitget signature
def generate_signature(timestamp, method, request_path, body):
    pre_hash = f"{timestamp}{method.upper()}{request_path}{body}"
    hmac_digest = hmac.new(BITGET_SECRET_KEY.encode(), pre_hash.encode(), hashlib.sha256).digest()
    return base64.b64encode(hmac_digest).decode()

# Auth headers
def get_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    sign = generate_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

# Format quantity to precision
def format_quantity(value, precision):
    quantized = Decimal(str(value)).quantize(Decimal("1." + "0" * precision), rounding=ROUND_DOWN)
    return format(quantized, f".{precision}f")

# Get symbol precision map from Bitget v2 API
def load_symbol_precisions():
    global symbol_precision_map
    try:
        url = f"{BITGET_API_URL}/api/v2/mix/market/symbols"
        response = requests.get(url)
        data = response.json()
        for item in data.get("data", []):
            symbol = item.get("symbol")
            size_place = int(item.get("sizePlace", 3))
            symbol_precision_map[symbol] = size_place
    except Exception as e:
        print(f"❌ Failed to load symbol metadata: {e}")

# Get available balance
def get_available_balance():
    try:
        path = "/api/v2/mix/account/accounts"
        url = BITGET_API_URL + path + "?productType=umcbl"
        headers = get_headers("GET", path)
        res = requests.get(url, headers=headers)
        balances = res.json().get("data", [])
        for asset in balances:
            if asset.get("marginCoin") == "USDT":
                return float(asset.get("available", 0))
    except Exception as e:
        print(f"❌ Balance fetch error: {e}")
    return 0

# Place order on Bitget
def place_futures_order(symbol, side, quantity, leverage):
    path = "/api/v2/mix/order/place-order"
    url = BITGET_API_URL + path
    body_data = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": side,
        "orderType": "market",
        "size": quantity,
        "leverage": str(leverage),
        "productType": "umcbl",
        "marginMode": "isolated"
    }
    body_json = json.dumps(body_data)
    headers = get_headers("POST", path, body_json)
    response = requests.post(url, headers=headers, json=body_data)
    return response.json()

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    load_symbol_precisions()

@client.event
async def on_message(message):
    if message.author.bot or message.channel.id != ALERT_CHANNEL_ID:
        return

    content = message.content.upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        await message.channel.send("🟨 Signal received")
        try:
            parts = content.split()
            raw_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = f"{raw_symbol}USDT_UMCBL"

            side = "buy"
            if "SHORT" in parts[0] or "(SHORT)" in content:
                side = "sell"

            leverage = DEFAULT_LEVERAGE
            if "LEVERAGE" in parts:
                i = parts.index("LEVERAGE")
                try:
                    leverage = int(parts[i + 1].replace("X", ""))
                except:
                    pass

            i = parts.index("BUYZONE")
            entry_low = float(parts[i + 1].replace("–", "-").replace("—", "-"))
            entry_high = float(parts[i + 3]) if parts[i + 2] == "-" else float(parts[i + 2])
            entry_price = (entry_low + entry_high) / 2

            balance = get_available_balance()
            trade_value = balance * TRADE_AMOUNT_PERCENT
            raw_quantity = trade_value / entry_price

            precision = symbol_precision_map.get(symbol)
            if precision is None:
                await message.channel.send(f"❌ Metadata fetch failed for {symbol}")
                return

            quantity = format_quantity(raw_quantity, precision)

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry: {entry_price}")
            await message.channel.send(f"📦 Size: {quantity}")

            result = place_futures_order(symbol, side, quantity, leverage)
            if result.get("code") == "00000":
                await message.channel.send(f"✅ Bitget Order Placed: {symbol} x{leverage}")
            else:
                await message.channel.send(f"❌ Trade failed: {result}")

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
