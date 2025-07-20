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
TRADE_BALANCE = float(os.getenv("TRADE_AMOUNT", "200"))

BITGET_API_URL = "https://api.bitget.com"

# Discord setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# Sign Bitget requests
def generate_signature(timestamp, method, request_path, body):
    pre_hash = f"{timestamp}{method.upper()}{request_path}{body}"
    hmac_digest = hmac.new(
        BITGET_SECRET_KEY.encode(),
        pre_hash.encode(),
        hashlib.sha256
    ).digest()
    return base64.b64encode(hmac_digest).decode()

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

def place_futures_order(symbol, side, quantity, leverage):
    path = "/api/v2/mix/order/place-order"
    url = BITGET_API_URL + path
    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": side,
        "orderType": "market",
        "size": str(quantity),
        "leverage": str(leverage),
        "productType": "umcbl",
        "marginMode": "isolated"
    }
    headers = get_headers("POST", path, json.dumps(body))
    resp = requests.post(url, headers=headers, json=body)
    return resp.json()

def place_plan_order(symbol, trigger_price, side, size, plan_type):
    path = "/api/v2/mix/order/place-plan-order"
    url = BITGET_API_URL + path
    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "triggerPrice": str(trigger_price),
        "triggerType": "mark_price",
        "side": side,
        "orderType": "market",
        "size": str(size),
        "planType": plan_type,
        "marginMode": "isolated",
        "productType": "umcbl"
    }
    headers = get_headers("POST", path, json.dumps(body))
    resp = requests.post(url, headers=headers, json=body)
    return resp.json()

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot or message.channel.id != ALERT_CHANNEL_ID:
        return

    content = message.content.replace("–", "-").upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        await message.channel.send("🟨 Signal received")
        try:
            parts = content.split()
            raw_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = f"{raw_symbol}USDT"

            side = "buy"
            plan_side = "close_long"
            if "SHORT" in parts[0] or "(SHORT)" in content:
                side = "sell"
                plan_side = "close_short"

            leverage = DEFAULT_LEVERAGE
            if "LEVERAGE" in parts:
                i = parts.index("LEVERAGE")
                leverage = int(parts[i + 1].replace("X", ""))

            i = parts.index("BUYZONE")
            entry_low = float(parts[i + 1])
            entry_high = float(parts[i + 3]) if parts[i + 2] == "-" else float(parts[i + 2])
            entry_price = (entry_low + entry_high) / 2

            targets = []
            stop = 0.0
            tp_index = parts.index("TARGETS") + 1
            for idx in range(tp_index, len(parts)):
                val = parts[idx]
                if val == "STOP":
                    stop = float(parts[idx + 1])
                    break
                try:
                    targets.append(float(val))
                except:
                    continue

            size = round(TRADE_BALANCE / entry_price, 3)

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {side.upper()}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry_price}")
            await message.channel.send(f"📦 Qty: {size}")

            result = place_futures_order(symbol, side, size, leverage)

            if result.get("code") == "00000":
                await message.channel.send(f"✅ Order Placed: {symbol} x{leverage} [{side.upper()}]")

                tp_shares = [0.5, 0.2, 0.15, 0.1, 0.05]
                for i in range(min(5, len(targets))):
                    tp_qty = round(size * tp_shares[i], 3)
                    resp = place_plan_order(symbol, targets[i], plan_side, tp_qty, "profit_plan")
                    await message.channel.send(f"📈 TP @{targets[i]}: {resp.get('msg', 'unknown')}")

                if stop:
                    resp = place_plan_order(symbol, stop, plan_side, size, "loss_plan")
                    await message.channel.send(f"🛑 SL @{stop}: {resp.get('msg', 'unknown')}")

            else:
                await message.channel.send(f"❌ Trade Failed: {result}")

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
