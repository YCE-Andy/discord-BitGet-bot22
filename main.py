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
    hmac_digest = hmac.new(BITGET_SECRET_KEY.encode(), pre_hash.encode(), hashlib.sha256).digest()
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
    response = requests.post(url, headers=headers, json=body_data)
    return response.json()

def place_tp_sl(symbol, entry_price, targets, stop_loss, side):
    path = "/api/v2/mix/order/place-plan-order"
    url = BITGET_API_URL + path

    tp_sizes = [0.5, 0.2, 0.15, 0.1, 0.05]
    tp_results = []

    for i, tp in enumerate(targets[:5]):
        tp_body = {
            "symbol": symbol,
            "marginCoin": "USDT",
            "size": str(round(TRADE_AMOUNT / entry_price * tp_sizes[i], 3)),
            "side": side,
            "orderType": "market",
            "triggerPrice": str(tp),
            "triggerType": "market_price",
            "executePrice": str(tp),
            "planType": "profit_plan",
            "marginMode": "isolated",
            "productType": "umcbl"
        }
        body_json = json.dumps(tp_body)
        headers = get_headers("POST", path, body_json)
        res = requests.post(url, headers=headers, json=tp_body)
        tp_results.append((tp, res.json()))

    sl_body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": str(round(TRADE_AMOUNT / entry_price, 3)),
        "side": "sell" if side == "buy" else "buy",
        "orderType": "market",
        "triggerPrice": str(stop_loss),
        "triggerType": "market_price",
        "executePrice": str(stop_loss),
        "planType": "loss_plan",
        "marginMode": "isolated",
        "productType": "umcbl"
    }
    sl_json = json.dumps(sl_body)
    headers = get_headers("POST", path, sl_json)
    sl_result = requests.post(url, headers=headers, json=sl_body).json()
    return tp_results, sl_result

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
            quantity = round(TRADE_AMOUNT / entry_price, 3)

            stop = float(parts[parts.index("STOP") + 1])

            targets = []
            i = parts.index("TARGETS") + 1
            while i < len(parts) and parts[i].replace('.', '', 1).isdigit():
                targets.append(float(parts[i]))
                i += 1

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry_price}")
            await message.channel.send(f"📦 Order size: {quantity}")

            result = place_futures_order(symbol, side, quantity, leverage)

            if result.get("code") == "00000":
                await message.channel.send(f"✅ Bitget Order Placed: {symbol} x{leverage} [{side.upper()}]")
                tp_results, sl_result = place_tp_sl(symbol, entry_price, targets, stop, side)
                for tp, r in tp_results:
                    await message.channel.send(f"📈 TP @{tp}: {'✅' if r.get('code') == '00000' else '❌ ' + str(r)}")
                await message.channel.send(f"🛑 SL @{stop}: {'✅' if sl_result.get('code') == '00000' else '❌ ' + str(sl_result)}")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
