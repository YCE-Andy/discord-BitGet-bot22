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

def get_available_balance():
    path = "/api/mix/v1/account/account"
    url = f"{BITGET_API_URL}{path}?productType=umcbl"
    headers = get_headers("GET", path)
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        for acc in data.get("data", []):
            if acc["marginCoin"] == "USDT":
                return float(acc["available"])
    except Exception as e:
        print(f"⚠️ Error fetching balance: {e}")
    return 0.0

# Place futures order
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

    for attempt in range(3):
        try:
            print(f"📤 Placing Bitget order: {body_json}")
            response = requests.post(url, headers=headers, json=body_data)
            return response.json()
        except Exception as e:
            print(f"⚠️ Bitget API call failed (attempt {attempt+1}): {e}")
            time.sleep(3)
    return {"error": "All attempts to place order failed."}

def place_tp_order(symbol, qty, price):
    path = "/api/v2/mix/order/place-order"
    url = BITGET_API_URL + path
    body_data = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": "sell",
        "orderType": "limit",
        "price": str(price),
        "size": str(qty),
        "marginMode": "isolated",
        "timeInForceValue": "normal",
        "productType": "umcbl"
    }
    body_json = json.dumps(body_data)
    headers = get_headers("POST", path, body_json)
    return requests.post(url, headers=headers, json=body_data).json()

def place_stop_loss(symbol, qty, stop_price):
    path = "/api/v2/mix/plan/place-plan"
    url = BITGET_API_URL + path
    body_data = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": "sell",
        "orderType": "market",
        "triggerPrice": str(stop_price),
        "triggerType": "fill_price",
        "size": str(qty),
        "marginMode": "isolated",
        "executePrice": "",
        "productType": "umcbl"
    }
    body_json = json.dumps(body_data)
    headers = get_headers("POST", path, body_json)
    return requests.post(url, headers=headers, json=body_data).json()

# Discord bot events
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
            entry_price = (entry_low + entry_high) / 2

            balance = get_available_balance()
            notional = balance * 0.2
            quantity = round(notional / entry_price, 3)

            stop = float(parts[parts.index("STOP") + 1])
            target_start = parts.index("TARGETS") + 1
            target_end = parts.index("STOP")
            targets = [float(x) for x in parts[target_start:target_end] if x.replace('.', '', 1).isdigit()]

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry_price}")
            await message.channel.send(f"📦 Order size: {quantity}")

            result = place_futures_order(symbol, side, quantity, leverage)

            if result.get("code") == "00000":
                await message.channel.send(f"✅ Bitget Order Placed: {symbol} x{leverage} [{side.upper()}]")

                # Place TPs
                tp_ratios = [0.5, 0.2, 0.15, 0.1, 0.05]
                for i in range(min(5, len(targets))):
                    tp_qty = round(quantity * tp_ratios[i], 3)
                    tp_price = targets[i]
                    tp_result = place_tp_order(symbol, tp_qty, tp_price)
                    await message.channel.send(f"🎯 TP{i+1} @ {tp_price}: {tp_result.get('msg', tp_result)}")

                # Place SL
                sl_result = place_stop_loss(symbol, quantity, stop)
                await message.channel.send(f"🛡 Stop @ {stop}: {sl_result.get('msg', sl_result)}")

            else:
                await message.channel.send(f"❌ Trade Failed: {result}")

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

# Start bot
client.run(DISCORD_BOT_TOKEN)
