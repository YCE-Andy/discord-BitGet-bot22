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

TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "200"))
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
            print(f"\U0001f4e4 Placing Bitget order: {body_json}")
            response = requests.post(url, headers=headers, json=body_data)
            return response.json()
        except Exception as e:
            print(f"⚠️ Bitget API call failed (attempt {attempt+1}): {e}")
            time.sleep(3)
    return {"error": "All attempts to place order failed."}

# Place take-profit or stop-loss plan

def place_plan_order(symbol, trigger_price, size, plan_type, side):
    path = "/api/v2/mix/order/place-plan-order"
    url = BITGET_API_URL + path
    body_data = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": str(size),
        "triggerPrice": str(trigger_price),
        "executePrice": str(trigger_price),
        "triggerType": "fill_price",
        "orderType": "market",
        "planType": plan_type,
        "side": side,
        "marginMode": "isolated",
        "productType": "umcbl"
    }
    body_json = json.dumps(body_data)
    headers = get_headers("POST", path, body_json)
    try:
        response = requests.post(url, headers=headers, json=body_data)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

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
            api_symbol = f"{raw_symbol}USDT_UMCBL"

            side = "buy"
            close_side = "close_long"
            if "SHORT" in parts[0] or "(SHORT)" in content:
                side = "sell"
                close_side = "close_short"

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

            targets = []
            if "TARGETS" in parts:
                i = parts.index("TARGETS") + 1
                while i < len(parts) and parts[i].replace(".", "").isdigit():
                    targets.append(float(parts[i]))
                    i += 1

            stop = None
            if "STOP" in parts:
                i = parts.index("STOP")
                stop = float(parts[i + 1])

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry_price}")
            await message.channel.send(f"📦 Order size: {quantity}")

            result = place_futures_order(api_symbol, side, quantity, leverage)

            if result.get("code") == "00000":
                await message.channel.send(f"✅ Bitget Order Placed: {symbol} x{leverage} [{side.upper()}]")

                # Place TP orders (50%, 20%, 15%, 10%, 5%)
                tp_sizes = [0.5, 0.2, 0.15, 0.1, 0.05]
                for i, tp in enumerate(targets[:5]):
                    tp_qty = round(quantity * tp_sizes[i], 3)
                    tp_result = place_plan_order(api_symbol, tp, tp_qty, "profit_plan", close_side)
                    msg = f"📈 TP @{tp}: {tp_result.get('msg', tp_result)}"
                    await message.channel.send(msg)

                # Place SL order
                if stop:
                    sl_result = place_plan_order(api_symbol, stop, quantity, "loss_plan", close_side)
                    msg = f"🛑 SL @{stop}: {sl_result.get('msg', sl_result)}"
                    await message.channel.send(msg)
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

# Start the bot
client.run(DISCORD_BOT_TOKEN)
