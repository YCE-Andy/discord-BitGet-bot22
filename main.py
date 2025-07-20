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

TRADE_PERCENT = 0.2  # 20% of available balance
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

# Get balance
def get_balance():
    try:
        path = "/api/v2/mix/account/accounts?productType=umcbl"
        url = BITGET_API_URL + path
        headers = get_headers("GET", path)
        res = requests.get(url, headers=headers)
        data = res.json()
        for acc in data.get("data", []):
            if acc.get("marginCoin") == "USDT":
                return float(acc.get("available", 0))
    except Exception as e:
        print("Balance error:", e)
    return 0

# Place futures market order
def place_futures_order(symbol, side, quantity, leverage):
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
    try:
        print(f"📤 Order body: {body_json}")
        response = requests.post(url, headers=headers, json=body_data)
        return response.json()
    except Exception as e:
        print("❌ Order failed:", e)
        return {"code": "ERROR", "msg": str(e)}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot or message.channel.id != ALERT_CHANNEL_ID:
        return

    content = message.content.upper().replace("–", "-")
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        await message.channel.send("🟨 Signal received")
        try:
            parts = content.split()
            raw_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = f"{raw_symbol}USDT"

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
            entry_low = float(parts[i + 1])
            entry_high = float(parts[i + 3]) if parts[i + 2] == "-" else float(parts[i + 2])
            entry = round((entry_low + entry_high) / 2, 6)

            stop_index = parts.index("STOP")
            stop = float(parts[stop_index + 1])

            target_lines = parts[parts.index("TARGETS") + 1:stop_index]
            targets = [float(t) for t in target_lines if t.replace('.', '', 1).isdigit()]
            targets = targets[:5]

            balance = get_balance()
            qty = round((balance * TRADE_PERCENT) / entry, 3)

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry: {entry}")
            await message.channel.send(f"📦 Qty: {qty}")
            await message.channel.send(f"🎯 Targets: {targets}")
            await message.channel.send(f"🛡️ Stop: {stop}")

            result = place_futures_order(symbol, side, qty, leverage)

            if result.get("code") == "00000":
                await message.channel.send(f"✅ Order placed: {symbol} x{leverage} [{side.upper()}]")
            else:
                await message.channel.send(f"❌ Trade failed: {result}")

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

# Start bot
client.run(DISCORD_BOT_TOKEN)
