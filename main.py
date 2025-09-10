from dotenv import load_dotenv
import os
import discord
import re
import time
import hmac
import hashlib
import requests
import json

# Load env vars
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
BLOFIN_API_KEY = os.getenv("BLOFIN_API_KEY")
BLOFIN_API_SECRET = os.getenv("BLOFIN_API_SECRET")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT"))
LEVERAGE = int(os.getenv("LEVERAGE"))

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def sign_blofin_request(secret, timestamp, method, path, body):
    payload = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

def place_order(symbol, side, vol, leverage, tp=None, sl=None):
    path = "/api/v1/mix/order/place-order"
    url = f"https://api.blofin.com{path}"
    timestamp = str(int(time.time() * 1000))

    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": "open_long" if side == 1 else "open_short",
        "orderType": "market",
        "size": str(vol),
        "leverage": str(leverage),
        "presetTakeProfitPrice": str(tp) if tp else "",
        "presetStopLossPrice": str(sl) if sl else "",
        "marginMode": "isolated"
    }

    body_str = json.dumps(body, separators=(',', ':'))
    signature = sign_blofin_request(BLOFIN_API_SECRET, timestamp, "POST", path, body_str)

    headers = {
        "ApiKey": BLOFIN_API_KEY,
        "Request-Time": timestamp,
        "Signature": signature,
        "Content-Type": "application/json"
    }

    r = requests.post(url, headers=headers, data=body_str)
    print(f"🔁 Response: {r.status_code} | {r.text}")
    try:
        return r.json()
    except:
        return {"error": "Invalid JSON response from BloFin"}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID or message.author == client.user:
        return

    content = message.content
    print(f"📩 Message received: {content}")

    symbol_match = re.search(r"([A-Z]+USDT)", content)
    buyzone_match = re.search(r"BUYZONE\s+([\d.]+)\s*-\s*([\d.]+)", content)
    targets = re.findall(r"(?<=\n)0\.\d{3,}", content)
    stop_match = re.search(r"Stop\s+([\d.]+)", content)
    lev_match = re.search(r"Leverage\s*x?(\d+)", content)

    if not all([symbol_match, buyzone_match, targets, stop_match, lev_match]):
        await message.channel.send("⚠️ Could not parse trade command.")
        return

    symbol = symbol_match.group(1)
    buy_low = float(buyzone_match.group(1))
    buy_high = float(buyzone_match.group(2))
    tp_list = [float(t) for t in targets if float(t) > buy_high]
    sl_price = float(stop_match.group(1))
    leverage = int(lev_match.group(1))

    # ⚡ Trade anyway at market if within BUYZONE
    # No need to fetch market price — we assume signal is timed
    size = round((TRADE_AMOUNT * leverage) / buy_high, 3)
    order = place_order(symbol, side=1, vol=size, leverage=leverage, tp=tp_list[0] if tp_list else None, sl=sl_price)

    if order.get("code") == "0":
        await message.channel.send(f"✅ Trade Placed: {symbol} | Leverage x{leverage} | Size: {size}")
    else:
        await message.channel.send(f"❌ Trade Failed: {order}")

client.run(DISCORD_TOKEN)
