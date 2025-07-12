import os
import time
import hmac
import json
import hashlib
import requests
import discord
import asyncio

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "200"))

API_BASE = "https://contract.mexc.com"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def sign_request(params, secret):
    sorted_params = sorted(params.items())
    query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
    signature = hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    return signature

def get_symbol_precision(symbol):
    url = f"{API_BASE}/api/v1/contract/detail"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        for item in data["data"]:
            if item["symbol"] == symbol:
                return item["priceScale"], item["volScale"]
    except:
        pass
    return None, None

def place_futures_order(symbol, side, quantity, leverage):
    path = "/api/v1/private/order/submit"
    url = API_BASE + path
    timestamp = int(time.time() * 1000)

    params = {
        "api_key": MEXC_API_KEY,
        "req_time": timestamp,
        "market": symbol,
        "price": 0,
        "vol": quantity,
        "side": 1 if side.lower() == "buy" else 2,
        "type": 1,
        "open_type": 1,
        "position_id": 0,
        "leverage": leverage,
        "external_oid": str(timestamp)
    }

    params["sign"] = sign_request(params, MEXC_SECRET_KEY)
    headers = {'Content-Type': 'application/json'}

    print(f"🛠 Sending order: {params}")
    try:
        response = requests.post(url, headers=headers, json=params, timeout=10)
        return response.json()
    except requests.exceptions.Timeout:
        time.sleep(2)
        try:
            response = requests.post(url, headers=headers, json=params, timeout=10)
            return response.json()
        except Exception as e:
            return {"error": f"Retry failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id != ALERT_CHANNEL_ID:
        print("🟨 Message received")
        print(f"🚫 Wrong channel: {message.channel.id}")
        return

    content = message.content.upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        try:
            parts = content.split()
            raw_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = f"{raw_symbol}_USDT"
            side = "buy"
            leverage = DEFAULT_LEVERAGE

            if "LEVERAGE" in content:
                lev_index = parts.index("LEVERAGE")
                leverage = int(parts[lev_index + 1].replace("X", "").strip())

            buyzone_index = parts.index("BUYZONE")
            entry_low = float(parts[buyzone_index + 1])
            entry_high_raw = parts[buyzone_index + 3] if parts[buyzone_index + 2] == "-" else parts[buyzone_index + 2]
            entry_high = float(entry_high_raw)
            entry_price = (entry_low + entry_high) / 2

            price_precision, vol_precision = get_symbol_precision(symbol)
            if not price_precision or not vol_precision:
                await message.channel.send(f"❌ Unknown symbol or failed to fetch precision: {symbol}")
                return

            qty = round(TRADE_AMOUNT / entry_price, vol_precision)

            await message.channel.send(f"🔎 Parsed symbol: {symbol}")
            await asyncio.sleep(0.5)
            await message.channel.send(f"⚙️ Leverage detected: x{leverage}")
            await asyncio.sleep(0.5)
            await message.channel.send(f"💰 Entry price: {entry_price}")
            await asyncio.sleep(0.5)
            await message.channel.send(f"📐 Precision: price={price_precision}, vol={vol_precision}")
            await asyncio.sleep(0.5)
            await message.channel.send(f"📦 Quantity: {qty}")
            await asyncio.sleep(0.5)

            result = place_futures_order(symbol, side, qty, leverage)

            if result.get("success"):
                await message.channel.send(f"✅ Trade Executed: {symbol} x{leverage}")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")
        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
