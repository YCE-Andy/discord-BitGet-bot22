import os
import time
import hmac
import json
import hashlib
import base64
import requests
import discord
import asyncio

# Load environment variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

TRADE_PERCENT = 0.2  # Use 20% of available USDT
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))

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

def get_symbol_meta(symbol):
    try:
        path = "/api/v2/mix/market/symbols"
        url = BITGET_API_URL + path + "?productType=umcbl"
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        for item in data.get("data", []):
            if item.get("symbol", "").upper() == symbol.upper():
                return item
        print(f"⚠️ Symbol metadata not found for {symbol}")
        return None
    except Exception as e:
        print(f"❌ Metadata fetch error: {e}")
        return None

def get_balance():
    try:
        path = "/api/v2/mix/account/accounts?productType=umcbl"
        url = BITGET_API_URL + path
        headers = get_headers("GET", "/api/v2/mix/account/accounts?productType=umcbl")
        res = requests.get(url, headers=headers)
        data = res.json()
        usdt = next((a for a in data["data"] if a["marginCoin"] == "USDT"), None)
        return float(usdt["available"]) if usdt else 0
    except Exception as e:
        print(f"❌ Balance fetch error: {e}")
        return 0

def place_order(symbol, side, quantity, leverage):
    path = "/api/v2/mix/order/place-order"
    url = BITGET_API_URL + path
    body_data = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": side,
        "orderType": "market",
        "size": str(quantity),
        "leverage": str(leverage),
        "productType": "umcbl",
        "marginMode": "isolated"
    }
    body_json = json.dumps(body_data)
    headers = get_headers("POST", path, body_json)

    for attempt in range(3):
        try:
            print(f"📤 Placing Bitget order: {body_json}")
            response = requests.post(url, headers=headers, json=body_data)
            return response.json()
        except Exception as e:
            print(f"⚠️ Bitget API call failed (attempt {attempt+1}): {e}")
            time.sleep(3)
    return {"error": "All attempts to place order failed."}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot or message.channel.id != ALERT_CHANNEL_ID:
        return

    content = message.content.upper().replace("–", "-")  # Replace bad dash
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        await message.channel.send("🟨 Signal received")
        try:
            print("⏳ Full message:")
            print(message.content)

            parts = content.split()
            raw_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = f"{raw_symbol}USDT"
            side = "buy" if "SHORT" not in parts[0] and "(SHORT)" not in content else "sell"

            leverage = DEFAULT_LEVERAGE
            if "LEVERAGE" in parts:
                i = parts.index("LEVERAGE")
                try:
                    leverage = int(parts[i + 1].replace("X", ""))
                except:
                    pass

            i = parts.index("BUYZONE")
            entry_low = float(parts[i + 1])
            entry_high = float(parts[i + 3]) if parts[i + 2] == "-" else float(parts[i + 2])
            entry = round((entry_low + entry_high) / 2, 6)

            tstart = parts.index("TARGETS") + 1
            stop_index = parts.index("STOP")
            targets = [float(p) for p in parts[tstart:stop_index] if p.replace('.', '', 1).isdigit()]

            stop = float(parts[stop_index + 1])

            meta = get_symbol_meta(symbol)
            if not meta:
                await message.channel.send(f"❌ Symbol metadata not found for {symbol}")
                return

            precision = int(meta.get("pricePlace", 2))
            sizePrecision = int(meta.get("volumePlace", 3))

            balance = get_balance()
            qty = round((balance * TRADE_PERCENT) / entry, sizePrecision)

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry}")
            await message.channel.send(f"🎯 Targets: {targets[:5]}")
            await message.channel.send(f"🛡️ Stop: {stop}")
            await message.channel.send(f"📦 Order size: {qty}")

            result = place_order(symbol, side, qty, leverage)

            if result.get("code") == "00000":
                await message.channel.send(f"✅ Order Placed: {symbol} x{leverage} [{side.upper()}]")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")

        except Exception as e:
            print(f"❌ Exception: {e}")
            await message.channel.send(f"⚠️ Error: {str(e)}")

# Start bot
client.run(DISCORD_BOT_TOKEN)
