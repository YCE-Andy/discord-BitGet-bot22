import os
import time
import hmac
import json
import hashlib
import requests
import discord
import asyncio

# Load environment variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", 5))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 200))

API_BASE = "https://contract.mexc.com"

client = discord.Client(intents=discord.Intents.all())

# ----- MEXC signing
def sign_request(params, secret):
    sorted_params = sorted(params.items())
    query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
    signature = hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    return signature

# ----- Get precision info for symbol
def get_symbol_precision(symbol):
    url = f"{API_BASE}/api/v1/contract/detail"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        for item in data["data"]:
            if item["symbol"] == symbol:
                return item["priceScale"], item["volScale"]
    except Exception as e:
        print(f"[ERROR] Precision lookup failed: {e}")
    return None, None

# ----- Submit order to MEXC
def place_futures_order(symbol, side, quantity, leverage):
    path = "/api/v1/private/order/submit"
    url = API_BASE + path
    timestamp = int(time.time() * 1000)

    order_type = 1  # market
    open_type = 1   # cross margin

    params = {
        "api_key": MEXC_API_KEY,
        "req_time": timestamp,
        "market": symbol,
        "price": 0,
        "vol": quantity,
        "side": 1 if side.lower() == "buy" else 2,
        "type": order_type,
        "open_type": open_type,
        "position_id": 0,
        "leverage": leverage,
        "external_oid": str(timestamp)
    }

    params["sign"] = sign_request(params, MEXC_SECRET_KEY)
    headers = {'Content-Type': 'application/json'}

    try:
        print(f"🛠 Sending order: {params}")
        response = requests.post(url, headers=headers, json=params, timeout=10)
        return response.json()
    except requests.exceptions.Timeout:
        return {"error": "MEXC request timed out"}
    except Exception as e:
        return {"error": str(e)}

# ----- Discord: on_ready
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

# ----- Discord: on_message
@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id != ALERT_CHANNEL_ID:
        print("🚫 Wrong channel:", message.channel.id)
        return

    content = message.content.upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        await message.channel.send("🟨 Message received")
        try:
            parts = content.split()
            base = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = f"{base}_USDT"
            side = "buy"
            leverage = DEFAULT_LEVERAGE

            if "LEVERAGE" in parts:
                lev_index = parts.index("LEVERAGE")
                leverage = int(parts[lev_index + 1].replace("X", ""))

            buyzone_index = parts.index("BUYZONE")
            entry_low = float(parts[buyzone_index + 1])
            entry_high = float(parts[buyzone_index + 3] if parts[buyzone_index + 2] == "-" else parts[buyzone_index + 2])
            entry_price = (entry_low + entry_high) / 2

            await message.channel.send(f"🔎 Parsed symbol: {symbol}")
            await message.channel.send(f"⚙️ Leverage detected: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry_price}")

            price_precision, vol_precision = get_symbol_precision(symbol)
            if price_precision is None:
                await message.channel.send(f"❌ Symbol {symbol} not supported on MEXC Futures.")
                return

            qty = round(TRADE_AMOUNT / entry_price, vol_precision)
            await message.channel.send(f"📐 Precision: price={price_precision}, vol={vol_precision}")
            await message.channel.send(f"📦 Quantity: {qty}")

            result = place_futures_order(symbol, side, qty, leverage)

            if result.get("success"):
                await message.channel.send(f"✅ Trade Executed: {symbol} x{leverage}")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")
            await asyncio.sleep(2)

        except Exception as e:
            await message.channel.send(f"⚠️ Bot Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
