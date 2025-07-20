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

# Discord client setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# HMAC signature
def generate_signature(timestamp, method, request_path, body):
    pre_hash = f"{timestamp}{method.upper()}{request_path}{body}"
    hmac_digest = hmac.new(BITGET_SECRET_KEY.encode(), pre_hash.encode(), hashlib.sha256).digest()
    return base64.b64encode(hmac_digest).decode()

# Bitget auth headers
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

# Place market futures order
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
    body_json = json.dumps(body)
    headers = get_headers("POST", path, body_json)

    response = requests.post(url, headers=headers, data=body_json)
    return response.json()

# Create TP/SL plan
def place_plan_order(symbol, side, trigger_price, size, plan_type):
    path = "/api/v2/mix/order/place-plan-order"
    url = BITGET_API_URL + path
    plan_side = "close_long" if side == "sell" else "close_short"
    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": str(size),
        "triggerPrice": str(trigger_price),
        "executePrice": str(trigger_price),
        "triggerType": "market_price",
        "orderType": "market",
        "planType": plan_type,
        "marginMode": "isolated",
        "productType": "umcbl",
        "side": plan_side
    }
    body_json = json.dumps(body)
    headers = get_headers("POST", path, body_json)

    response = requests.post(url, headers=headers, data=body_json)
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

            # Buyzone parsing
            i = parts.index("BUYZONE")
            entry_low = float(parts[i + 1])
            entry_high = float(parts[i + 3]) if parts[i + 2] == "-" else float(parts[i + 2])
            entry_price = (entry_low + entry_high) / 2
            quantity = round(TRADE_AMOUNT / entry_price, 3)

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry_price}")
            await message.channel.send(f"📦 Qty: {quantity}")

            result = place_futures_order(symbol, side, quantity, leverage)
            if result.get("code") == "00000":
                await message.channel.send(f"✅ Order Placed: {symbol} x{leverage} [{side.upper()}]")

                # Extract target prices
                targets = []
                if "TARGETS" in parts:
                    idx = parts.index("TARGETS")
                    for j in range(idx + 1, len(parts)):
                        try:
                            t = float(parts[j])
                            targets.append(t)
                        except:
                            break

                stop_price = 0.0
                if "STOP" in parts:
                    stop_price = float(parts[parts.index("STOP") + 1])

                # TP %: 50, 20, 15, 10, 5
                tp_shares = [0.5, 0.2, 0.15, 0.1, 0.05]
                for k in range(min(5, len(targets))):
                    tp_qty = round(quantity * tp_shares[k], 3)
                    tp = place_plan_order(symbol, side, targets[k], tp_qty, "profit_plan")
                    status = "✅" if tp.get("code") == "00000" else f"❌ {tp.get('msg')}"
                    await message.channel.send(f"📈 TP @{targets[k]}: {status}")

                if stop_price > 0:
                    sl = place_plan_order(symbol, side, stop_price, quantity, "loss_plan")
                    sl_status = "✅" if sl.get("code") == "00000" else f"❌ {sl.get('msg')}"
                    await message.channel.send(f"🛑 SL @{stop_price}: {sl_status}")

            else:
                await message.channel.send(f"❌ Trade Failed: {result}")
        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

# Run bot
client.run(DISCORD_BOT_TOKEN)
