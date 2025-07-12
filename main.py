import os
import time
import hmac
import json
import hashlib
import requests
import discord
import asyncio

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 200))
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", 5))

API_BASE = "https://contract.mexc.com"
client = discord.Client(intents=discord.Intents.all())

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
        print(f"🔍 Raw /contract/detail response:\n{json.dumps(data, indent=2)}")
        for item in data["data"]:
            if item["symbol"] == symbol:
                print(f"✅ Found symbol: {symbol}")
                return item["priceScale"], item["volScale"]
        print(f"❌ Symbol {symbol} not found in MEXC contract list")
    except Exception as e:
        print(f"❌ Error fetching symbol precision: {e}")
    return None, None

def place_futures_order(symbol, side, quantity, leverage):
    path = "/api/v1/private/order/submit"
    url = API_BASE + path
    timestamp = int(time.time() * 1000)

    order_type = 1  # market
    open_type = 1   # cross

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
    except Exception as e:
        return {"error": f"MEXC request error: {str(e)}"}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id != SOURCE_CHANNEL_ID:
        print(f"🟨 Message received but ignored: Wrong channel ({message.channel.id})")
        return

    content = message.content.upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        try:
            parts = content.split()
            base_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = f"{base_symbol}_USDT"
            side = "buy"
            leverage = DEFAULT_LEVERAGE

            if "LEVERAGE" in content:
                lev_index = parts.index("LEVERAGE")
                leverage = int(parts[lev_index + 1].replace("X", ""))

            buyzone_index = parts.index("BUYZONE")
            entry_low = float(parts[buyzone_index + 1])
            entry_high = float(parts[buyzone_index + 3] if parts[buyzone_index + 2] == "-" else parts[buyzone_index + 2])
            entry_price = (entry_low + entry_high) / 2

            price_precision, vol_precision = get_symbol_precision(symbol)
            if price_precision is None:
                await message.channel.send(f"❌ Unknown symbol or failed to fetch precision: {symbol}")
                return

            qty = round(TRADE_AMOUNT / entry_price, vol_precision)
            await message.channel.send(
                f"🔎 Parsed symbol: {symbol}\n"
                f"⚙️ Leverage detected: x{leverage}\n"
                f"💰 Entry price: {entry_price}\n"
                f"📐 Precision: price={price_precision}, vol={vol_precision}\n"
                f"📦 Quantity: {qty}"
            )

            await asyncio.sleep(1)  # Let Discord send message before placing order

            result = place_futures_order(symbol, side, qty, leverage)

            if result.get("success") or result.get("code") == 0:
                await message.channel.send(f"✅ Trade Executed: {symbol} x{leverage}")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")
        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
