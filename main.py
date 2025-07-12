import os
import time
import hmac
import json
import hashlib
import requests
import discord

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 200))

API_BASE = "https://contract.mexc.com"
client = discord.Client(intents=discord.Intents.all())

def sign_request(params, secret):
    sorted_params = sorted(params.items())
    query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
    signature = hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    return signature

def get_symbol_precision(symbol):
    url = f"{API_BASE}/api/v1/contract/detail"
    response = requests.get(url)
    data = response.json()
    for item in data["data"]:
        if item["symbol"] == symbol:
            return item["priceScale"], item["volScale"]
    return None, None

def place_futures_order(symbol, side, quantity, leverage):
    url = f"{API_BASE}/api/v1/private/order/submit"
    timestamp = int(time.time() * 1000)
    order_type = 1  # Market order
    open_type = 1   # Cross margin

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
        response = requests.post(url, headers=headers, json=params)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    print("🟨 Message received")

    if message.channel.id != ALERT_CHANNEL_ID:
        print(f"🚫 Wrong channel: {message.channel.id}")
        return

    content = message.content.upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        try:
            parts = content.split()
            base_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = base_symbol + "_USDT"
            side = "buy"
            leverage = 5

            if "LEVERAGE" in parts:
                lev_index = parts.index("LEVERAGE")
                lev_value = parts[lev_index + 1].replace("X", "")
                leverage = int(lev_value)

            buyzone_index = parts.index("BUYZONE")
            entry_low = float(parts[buyzone_index + 1])
            if parts[buyzone_index + 2] == "-":
                entry_high = float(parts[buyzone_index + 3])
            else:
                entry_high = float(parts[buyzone_index + 2])
            entry_price = (entry_low + entry_high) / 2

            price_precision, vol_precision = get_symbol_precision(symbol)
            qty = round(TRADE_AMOUNT / entry_price, vol_precision or 3)

            await message.channel.send(
                f"🚀 Placing market order: BUY {symbol} ~{qty} @ {entry_price} with x{leverage}"
            )

            result = place_futures_order(symbol, side, qty, leverage)
            print("📤 Response:", result)

            if result.get("success"):
                await message.channel.send(f"✅ Trade Executed: {symbol} x{leverage}")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")
        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")
            print("❌ Exception:", str(e))

client.run(DISCORD_BOT_TOKEN)
