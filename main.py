import os
import time
import hmac
import json
import hashlib
import base64
import requests
import discord
import asyncio

# ENV variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "200"))
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))
BITGET_API_URL = "https://api.bitget.com"

# Discord client
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# Signature generation

def generate_signature(timestamp, method, request_path, body):
    pre_hash = f"{timestamp}{method.upper()}{request_path}{body}"
    digest = hmac.new(BITGET_SECRET_KEY.encode(), pre_hash.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()

# Headers for Bitget

def get_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

# Entry order

def place_futures_order(symbol, side, quantity, leverage):
    url = f"{BITGET_API_URL}/api/v2/mix/order/place-order"
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
    headers = get_headers("POST", "/api/v2/mix/order/place-order", json.dumps(body))
    response = requests.post(url, headers=headers, json=body)
    return response.json()

# Plan orders: TP and SL

def place_plan_order(symbol, trigger_price, size, side, plan_type):
    url = f"{BITGET_API_URL}/api/v2/mix/order/place-plan-order"
    plan_side = "open_long" if side == "buy" else "open_short"
    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": str(size),
        "side": plan_side,
        "planType": plan_type,
        "triggerPrice": str(trigger_price),
        "executePrice": str(trigger_price),
        "triggerType": "mark_price",
        "orderType": "market",
        "marginMode": "isolated",
        "productType": "umcbl"
    }
    headers = get_headers("POST", "/api/v2/mix/order/place-plan-order", json.dumps(body))
    response = requests.post(url, headers=headers, json=body)
    return response.json()

# Discord events
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
            side = "buy" if "SHORT" not in parts[0] and "(SHORT)" not in content else "sell"
            leverage = DEFAULT_LEVERAGE

            if "LEVERAGE" in parts:
                idx = parts.index("LEVERAGE")
                try:
                    leverage = int(parts[idx + 1].replace("X", ""))
                except:
                    pass

            i = parts.index("BUYZONE")
            entry_low = float(parts[i + 1].replace("–", "-").replace("—", "-"))
            entry_high = float(parts[i + 3]) if parts[i + 2] == "-" else float(parts[i + 2])
            entry_price = (entry_low + entry_high) / 2
            quantity = round(TRADE_AMOUNT / entry_price, 3)

            t_start = parts.index("TARGETS") + 1
            stop_index = parts.index("STOP")
            targets = [float(x) for x in parts[t_start:stop_index]]
            stop = float(parts[stop_index + 1])

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry_price}")
            await message.channel.send(f"📦 Order size: {quantity}")

            entry = place_futures_order(symbol, side, quantity, leverage)
            if entry.get("code") != "00000":
                await message.channel.send(f"❌ Trade Failed: {entry}")
                return

            await message.channel.send(f"✅ Bitget Order Placed: {symbol} x{leverage} [{side.upper()}]")

            tp_sizes = [0.5, 0.2, 0.15, 0.1, 0.05]
            for i in range(min(5, len(targets))):
                tp_qty = round(quantity * tp_sizes[i], 3)
                tp_result = place_plan_order(symbol, targets[i], tp_qty, side, "profit_plan")
                msg = f"📈 TP @{targets[i]}: {'✅' if tp_result.get('code') == '00000' else '❌ ' + tp_result.get('msg', 'Unknown')}"
                await message.channel.send(msg)

            sl_result = place_plan_order(symbol, stop, quantity, side, "loss_plan")
            msg = f"🛑 SL @{stop}: {'✅' if sl_result.get('code') == '00000' else '❌ ' + sl_result.get('msg', 'Unknown')}"
            await message.channel.send(msg)

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

# Run
client.run(DISCORD_BOT_TOKEN)
