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

# Fetch USDT balance
def get_balance():
    url = BITGET_API_URL + "/api/v2/account/accounts"
    headers = get_headers("GET", "/api/v2/account/accounts")
    try:
        res = requests.get(url, headers=headers).json()
        for acct in res.get("data", []):
            if acct.get("marginCoin") == "USDT":
                return float(acct.get("available", 0))
    except:
        pass
    return 0

# Place market order
def place_market_order(symbol, side, quantity, leverage):
    url = BITGET_API_URL + "/api/v2/mix/order/place-order"
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
    headers = get_headers("POST", "/api/v2/mix/order/place-order", body_json)
    return requests.post(url, headers=headers, json=body).json()

# Place TP/SL orders
def place_trigger_order(symbol, trigger_price, side, exec_side, size, order_type="limit"):
    url = BITGET_API_URL + "/api/v2/mix/order/place-plan-order"
    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "triggerPrice": str(trigger_price),
        "side": exec_side,
        "size": str(size),
        "orderType": order_type,
        "triggerType": "mark_price",
        "executePrice": str(trigger_price),
        "marginMode": "isolated",
        "productType": "umcbl",
        "planType": "profit_plan" if side == "tp" else "loss_plan"
    }
    body_json = json.dumps(body)
    headers = get_headers("POST", "/api/v2/mix/order/place-plan-order", body_json)
    return requests.post(url, headers=headers, json=body).json()

# Discord Events
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
            parts = content.replace("\n", " ").split()
            raw_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = f"{raw_symbol}USDT"
            side = "buy"
            if "SHORT" in parts[0] or "(SHORT)" in content:
                side = "sell"

            # Leverage
            leverage = DEFAULT_LEVERAGE
            if "LEVERAGE" in parts:
                i = parts.index("LEVERAGE")
                try:
                    leverage = int(parts[i + 1].replace("X", ""))
                except:
                    pass

            # Buyzone
            i = parts.index("BUYZONE")
            entry_low = float(parts[i + 1].replace("–", "-"))
            entry_high = float(parts[i + 3]) if parts[i + 2] == "-" else float(parts[i + 2])
            entry_price = (entry_low + entry_high) / 2

            # Stop
            stop = float(parts[parts.index("STOP") + 1])

            # Targets
            target_index = parts.index("TARGETS") + 1
            targets = []
            for j in range(target_index, len(parts)):
                try:
                    targets.append(float(parts[j]))
                except:
                    break
            targets = targets[:5]  # Max 5 targets

            # Quantity = 20% balance
            balance = get_balance()
            if balance <= 0:
                await message.channel.send("❌ No USDT balance available.")
                return
            usdt = balance * 0.2
            quantity = round(usdt / entry_price, 3)

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Direction: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry: {entry_price}")
            await message.channel.send(f"📦 Size: {quantity}")
            await message.channel.send(f"🎯 Targets: {targets}")
            await message.channel.send(f"🛑 Stop: {stop}")

            result = place_market_order(symbol + "_UMCBL", side, quantity, leverage)
            if result.get("code") != "00000":
                await message.channel.send(f"❌ Trade Failed: {result}")
                return

            await message.channel.send("✅ Trade placed!")

            # TP Partial Orders
            tp_shares = [0.5, 0.2, 0.15, 0.1, 0.05]
            for i in range(min(5, len(targets))):
                size = round(quantity * tp_shares[i], 3)
                tp_result = place_trigger_order(symbol + "_UMCBL", targets[i], "tp", "sell" if side == "buy" else "buy", size)
                await message.channel.send(f"📤 TP{i+1}: {tp_result.get('msg', 'Error')}")

            # SL
            sl_result = place_trigger_order(symbol + "_UMCBL", stop, "sl", "sell" if side == "buy" else "buy", quantity)
            await message.channel.send(f"📛 SL: {sl_result.get('msg', 'Error')}")

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {e}")

client.run(DISCORD_BOT_TOKEN)
