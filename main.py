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
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "200"))
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))

API_BASE = "https://contract.mexc.com"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

def sign_request(params, secret):
    sorted_params = sorted(params.items())
    query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
    signature = hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    return signature

def get_symbol_precision(symbol):
    try:
        url = f"{API_BASE}/api/v1/contract/detail"
        response = requests.get(url, timeout=10)
        data = response.json()
        for item in data["data"]:
            if item["symbol"] == symbol:
                return item["priceScale"], item["volScale"]
    except Exception as e:
        print(f"❌ Precision fetch error: {e}")
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
    headers = {"Content-Type": "application/json"}

    for attempt in range(3):
        try:
            print(f"🛠 Sending order: {params}")
            response = requests.post(url, headers=headers, json=params, timeout=30)
            return response.json()
        except Exception as e:
            print(f"⚠️ Attempt {attempt+1} failed: {e}")
            time.sleep(3)
    return {"error": f"MEXC request error: All attempts failed"}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id != ALERT_CHANNEL_ID:
        print(f"🟨 Message received but ignored: Wrong channel ({message.channel.id})")
        return

    content = message.content.upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        await message.channel.send("🟨 Message received")
        try:
            parts = content.split()
            raw_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = raw_symbol + "_USDT"
            side = "buy"
            leverage = DEFAULT_LEVERAGE

            if "LEVERAGE" in parts:
                i = parts.index("LEVERAGE")
                try:
                    leverage = int(parts[i + 1].replace("X", ""))
                except:
                    pass

            i = parts.index("BUYZONE")
            entry_low = float(parts[i + 1])
            if parts[i + 2] == "-":
                entry_high = float(parts[i + 3])
            else:
                entry_high = float(parts[i + 2])

            entry_price = (entry_low + entry_high) / 2
            price_precision, vol_precision = get_symbol_precision(symbol)

            if price_precision is None or vol_precision is None:
                await message.channel.send(f"❌ Unknown symbol or failed to fetch precision: {symbol}")
                return

            quantity = round(TRADE_AMOUNT / entry_price, vol_precision)

            await message.channel.send(f"🔎 Parsed symbol: {symbol}")
            await message.channel.send(f"⚙️ Leverage detected: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry_price}")
            await message.channel.send(f"📐 Precision: price={price_precision}, vol={vol_precision}")
            await message.channel.send(f"📦 Quantity: {quantity}")

            result = place_futures_order(symbol, side, quantity, leverage)

            if result.get("success"):
                await message.channel.send(f"✅ Trade Executed: {symbol} x{leverage}")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")

            await asyncio.sleep(1)  # Let Discord send

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
