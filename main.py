import os
import time
import hmac
import json
import hashlib
import base64
import requests
import discord
import asyncio

# ENV VARS
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "200"))
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))

BITGET_API_URL = "https://api.bitget.com"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# TELEGRAM ALERT
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"❌ Telegram alert error: {e}")

# SIGNATURE
def generate_signature(timestamp, method, request_path, body):
    pre_hash = f"{timestamp}{method.upper()}{request_path}{body}"
    digest = hmac.new(BITGET_SECRET_KEY.encode(), pre_hash.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()

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

def place_market_order(symbol, side, quantity, leverage):
    path = "/api/v2/mix/order/place-order"
    url = BITGET_API_URL + path
    data = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": side,
        "orderType": "market",
        "size": str(quantity),
        "leverage": str(leverage),
        "productType": "umcbl",
        "marginMode": "isolated"
    }
    headers = get_headers("POST", path, json.dumps(data))
    try:
        resp = requests.post(url, headers=headers, json=data)
        return resp.json()
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
    if not (("BUYZONE" in content or "SELLZONE" in content) and "TARGETS" in content and "STOP" in content):
        return

    await message.channel.send("🟨 Signal received")
    send_telegram_alert("🟨 Signal received")

    try:
        parts = content.split()
        symbol = parts[0].replace("PERP", "").replace("USDT", "") + "USDT"
        side = "buy" if "BUYZONE" in content else "sell"
        leverage = DEFAULT_LEVERAGE

        if "LEVERAGE" in parts:
            i = parts.index("LEVERAGE")
            try:
                leverage = int(parts[i + 1].replace("X", ""))
            except:
                pass

        zone_idx = parts.index("BUYZONE") if "BUYZONE" in parts else parts.index("SELLZONE")
        entry_low = float(parts[zone_idx + 1])
        entry_high = float(parts[zone_idx + 3]) if parts[zone_idx + 2] == "-" else float(parts[zone_idx + 2])
        entry_price = (entry_low + entry_high) / 2
        quantity = round(TRADE_AMOUNT / entry_price, 3)

        stop_idx = parts.index("STOP")
        stop_price = float(parts[stop_idx + 1])

        target_idx = parts.index("TARGETS")
        targets = []
        for i in range(target_idx + 1, len(parts)):
            if parts[i].replace(".", "", 1).isdigit():
                targets.append(float(parts[i]))
            else:
                break
        targets = targets[:4]

        # Execute order
        await message.channel.send(f"📤 {side.upper()} {symbol} @ {entry_price} x{leverage} for {quantity}")
        result = place_market_order(symbol, side, quantity, leverage)

        if result.get("code") == "00000":
            await message.channel.send(f"✅ Order placed.")
            send_telegram_alert(f"✅ Bitget Order Placed\n{symbol} {side.upper()} x{leverage}\nEntry: {entry_price}\nTPs: {targets}\nSL: {stop_price}")
        else:
            await message.channel.send(f"❌ Trade failed: {result}")
            send_telegram_alert(f"❌ Trade failed: {result}")

    except Exception as e:
        await message.channel.send(f"⚠️ Error: {e}")
        send_telegram_alert(f"⚠️ Error: {e}")

client.run(DISCORD_BOT_TOKEN)
