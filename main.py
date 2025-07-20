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
def generate_auth_headers(method, path, body_dict, timestamp):
    body = json.dumps(body_dict) if body_dict else ""
    sign = generate_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

# Place market order
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
    headers = generate_auth_headers("POST", path, body, str(int(time.time() * 1000)))

    try:
        response = requests.post(url, headers=headers, json=body)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# Place plan order (TP/SL)
def place_plan_order(symbol, trigger_price, side, quantity, plan_type):
    path = "/api/v2/mix/order/place-plan-order"
    url = BITGET_API_URL + path
    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": str(quantity),
        "side": side,
        "triggerPrice": str(trigger_price),
        "triggerType": "market_price",
        "planType": plan_type,
        "orderType": "market"
    }
    headers = generate_auth_headers("POST", path, body, str(int(time.time() * 1000)))

    try:
        response = requests.post(url, headers=headers, json=body)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

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
            entry_low = float(parts[i + 1].replace(",", "").replace("–", "-"))
            entry_high = float(parts[i + 3] if parts[i + 2] == "-" else parts[i + 2])
            entry_price = (entry_low + entry_high) / 2
            quantity = round(TRADE_AMOUNT / entry_price, 3)

            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry: {entry_price}")
            await message.channel.send(f"📦 Size: {quantity}")

            result = place_futures_order(symbol, side, quantity, leverage)
            if result.get("code") == "00000":
                await message.channel.send(f"✅ Bitget Order Placed: {symbol} x{leverage} [{side.upper()}]")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")
                return

            # Parse targets
            i = parts.index("TARGETS")
            targets = []
            for j in range(i + 1, len(parts)):
                try:
                    if parts[j] == "STOP":
                        break
                    targets.append(float(parts[j]))
                except:
                    break

            stop = float(parts[parts.index("STOP") + 1])
            sizes = [0.5, 0.2, 0.15, 0.1, 0.05]

            for i in range(min(5, len(targets))):
                tp_result = place_plan_order(symbol, targets[i], "sell" if side == "buy" else "buy", round(quantity * sizes[i], 3), "profit_plan")
                await message.channel.send(f"📈 TP @{targets[i]}: {tp_result}")

            sl_result = place_plan_order(symbol, stop, "sell" if side == "buy" else "buy", quantity, "loss_plan")
            await message.channel.send(f"🛑 SL @{stop}: {sl_result}")

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

# Start bot
client.run(DISCORD_BOT_TOKEN)
