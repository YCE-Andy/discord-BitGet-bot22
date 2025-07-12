import os
import time
import hmac
import json
import hashlib
import requests
import discord

# Environment variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
API_BASE = "https://contract.mexc.com"

TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "200"))

client = discord.Client(intents=discord.Intents.all())

def sign_request(params, secret):
    sorted_params = sorted(params.items())
    query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
    signature = hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    return signature

def get_symbol_precision(symbol):
    try:
        url = f"{API_BASE}/api/v1/contract/detail"
        response = requests.get(url)
        data = response.json()
        for item in data["data"]:
            if item["symbol"] == symbol:
                return item["priceScale"], item["volScale"]
    except Exception as e:
        print("❌ Error fetching precision:", str(e))
    return None, None

def place_futures_order(symbol, side, quantity, leverage):
    path = "/api/v1/private/order/submit"
    url = API_BASE + path
    timestamp = int(time.time() * 1000)

    order_type = 1  # 1 = market
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
        response = requests.post(url, headers=headers, data=json.dumps(params))
        print("📤 MEXC Response:", response.text)
        return response.json()
    except Exception as e:
        print("❗ MEXC Order Error:", str(e))
        return {"error": str(e)}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    print("🟨 Message received")

    if message.author.bot:
        print("🔕 Ignoring bot message")
        return

    if message.channel.id != ALERT_CHANNEL_ID:
        print(f"🚫 Wrong channel: {message.channel.id}")
        return

    print(f"📨 Message content: {message.content}")

    content = message.content.upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        try:
            parts = content.split()
            symbol = parts[0].replace("PERP", "").replace("USDT", "") + "_USDT"
            print(f"🔎 Parsed symbol: {symbol}")

            side = "buy"
            leverage = 5

            if "LEVERAGE" in content:
                lev_index = parts.index("LEVERAGE")
                leverage = int(parts[lev_index + 1].replace("X", ""))
                print(f"⚙️ Leverage detected: x{leverage}")

            buyzone_index = parts.index("BUYZONE")
            entry_low = float(parts[buyzone_index + 1])
            entry_high = float(parts[buyzone_index + 3] if parts[buyzone_index + 2] == "-" else parts[buyzone_index + 2])
            entry_price = (entry_low + entry_high) / 2
            print(f"💰 Entry price: {entry_price}")

            price_precision, vol_precision = get_symbol_precision(symbol)
            print(f"📐 Precision: price={price_precision}, vol={vol_precision}")
            qty = round(TRADE_AMOUNT / entry_price, vol_precision or 3)
            print(f"📦 Quantity: {qty}")

            await message.channel.send(f"🚀 Placing market order: BUY {symbol} ~{qty} @ {entry_price} with x{leverage}")
            result = place_futures_order(symbol, side, qty, leverage)

            if result.get("success"):
                await message.channel.send(f"✅ Trade Executed: {symbol} x{leverage}")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")
        except Exception as e:
            print("❗ Error parsing or executing trade:", str(e))
            await message.channel.send(f"⚠️ Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
