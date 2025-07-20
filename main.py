import os
import time
import hmac
import json
import hashlib
import base64
import requests
import discord
import asyncio

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "200"))
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))
BITGET_API_URL = "https://api.bitget.com"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

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
        response = requests.post(url, headers=headers, json=body_data)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def place_plan_order(symbol, price, size, side, plan_type):
    path = "/api/v2/mix/order/place-plan-order"
    url = BITGET_API_URL + path
    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "marginMode": "isolated",
        "orderType": "limit",
        "triggerType": "market_price",
        "planType": plan_type,
        "side": side,
        "price": price,
        "size": size,
        "triggerPrice": price,
        "productType": "umcbl"
    }
    headers = get_headers("POST", path, json.dumps(body))
    try:
        response = requests.post(url, headers=headers, json=body)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

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
                try:
                    leverage = int(parts[parts.index("LEVERAGE") + 1].replace("X", ""))
                except: pass

            i = parts.index("BUYZONE")
            entry_low = float(parts[i + 1])
            entry_high = float(parts[i + 3]) if parts[i + 2] == "-" else float(parts[i + 2])
            entry_price = (entry_low + entry_high) / 2
            quantity = round(TRADE_AMOUNT / entry_price, 3)

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry_price}")
            await message.channel.send(f"📦 Order size: {quantity}")

            result = place_futures_order(symbol, side, quantity, leverage)
            if result.get("code") == "00000":
                await message.channel.send(f"✅ Bitget Order Placed: {symbol} x{leverage} [{side.upper()}]")

                # Parse TP targets
                target_prices = []
                if "TARGETS" in parts:
                    idx = parts.index("TARGETS") + 1
                    while idx < len(parts) and parts[idx].replace('.', '', 1).isdigit():
                        target_prices.append(float(parts[idx]))
                        idx += 1

                # Parse SL
                stop_price = None
                if "STOP" in parts:
                    stop_price = float(parts[parts.index("STOP") + 1])

                tp_sizes = [0.5, 0.2, 0.15, 0.1, 0.05]
                for i, tp in enumerate(target_prices[:5]):
                    tp_size = round(quantity * tp_sizes[i], 3)
                    res = place_plan_order(symbol, tp, tp_size, side, "profit_plan")
                    await message.channel.send(f"📈 TP @{tp}: {res}")

                if stop_price:
                    sl_size = round(quantity, 3)
                    sl_res = place_plan_order(symbol, stop_price, sl_size, side, "loss_plan")
                    await message.channel.send(f"🛑 SL @{stop_price}: {sl_res}")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
