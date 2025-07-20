import os
import time
import hmac
import json
import hashlib
import base64
import requests
import discord
import asyncio
from decimal import Decimal, ROUND_DOWN

# Load environment variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))
TRADE_PERCENT = 0.2  # 20% of available balance

BITGET_API_URL = "https://api.bitget.com"

# Discord client setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# Signature generator
def generate_signature(timestamp, method, request_path, body):
    pre_hash = f"{timestamp}{method.upper()}{request_path}{body}"
    hmac_digest = hmac.new(
        BITGET_SECRET_KEY.encode(),
        pre_hash.encode(),
        hashlib.sha256
    ).digest()
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

# Get symbol metadata
def get_symbol_metadata():
    try:
        url = f"{BITGET_API_URL}/api/v2/mix/market/symbols?productType=umcbl"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        symbol_info = {}
        for item in data.get("data", []):
            symbol_info[item["symbol"]] = int(item["sizePlace"])
        return symbol_info
    except Exception as e:
        print(f"❌ Failed to fetch symbol metadata: {e}")
        return {}

# Get available balance
def get_available_balance():
    try:
        path = "/api/v2/mix/account/account"
        url = BITGET_API_URL + path + "?productType=umcbl&marginCoin=USDT"
        headers = get_headers("GET", path)
        response = requests.get(url, headers=headers)
        data = response.json()
        if data.get("code") == "00000":
            return float(data["data"].get("available", 0))
    except Exception as e:
        print(f"❌ Balance fetch error: {e}")
    return 0

# Format quantity to match symbol precision
def format_quantity(value, precision):
    return str(Decimal(value).quantize(Decimal(f"1.{'0'*precision}"), rounding=ROUND_DOWN))

# Place futures order
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

    try:
        print(f"📤 Sending Bitget order: {body_json}")
        response = requests.post(url, headers=headers, json=body_data)
        return response.json()
    except Exception as e:
        print(f"⚠️ Bitget API error: {e}")
        return {"error": str(e)}

# Discord event handlers
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

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

            symbol_precisions = get_symbol_metadata()
            if symbol not in symbol_precisions:
                await message.channel.send(f"❌ Metadata fetch failed for {symbol}")
                return

            available = get_available_balance()
            amount_to_trade = available * TRADE_PERCENT
            quantity = float(amount_to_trade) / entry_price
            quantity_str = format_quantity(quantity, symbol_precisions[symbol])

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry_price}")
            await message.channel.send(f"📦 Size: {quantity_str}")

            result = place_futures_order(symbol, side, quantity_str, leverage)

            if result.get("code") == "00000":
                await message.channel.send(f"✅ Bitget Order Placed: {symbol} x{leverage} [{side.upper()}]")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
