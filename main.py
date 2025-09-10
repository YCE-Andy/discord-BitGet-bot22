import os
import re
import time
import hmac
import json
import hashlib
import requests
import discord
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
BLOFIN_API_KEY = os.getenv("BLOFIN_API_KEY")
BLOFIN_API_SECRET = os.getenv("BLOFIN_API_SECRET")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT"))  # e.g., 500
LEVERAGE = int(os.getenv("LEVERAGE"))            # e.g., 10

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def sign_blofin_request(secret, timestamp, method, path, body=''):
    payload = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

def place_order(symbol, size, leverage, tp, sl):
    url_path = "/api/v1/trade/order"
    full_url = f"https://api.blofin.com{url_path}"
    timestamp = str(int(time.time() * 1000))

    body = {
        "instId": symbol,
        "marginMode": "isolated",
        "positionSide": "net",
        "side": "buy",
        "orderType": "market",
        "size": str(size),
        "reduceOnly": False,
        "clientOrderId": f"discord_{timestamp}",
        "tpTriggerPrice": str(tp),
        "tpOrderPrice": "-1",
        "slTriggerPrice": str(sl),
        "slOrderPrice": "-1"
    }

    body_json = json.dumps(body)
    signature = sign_blofin_request(BLOFIN_API_SECRET, timestamp, "POST", url_path, body_json)

    headers = {
        "ApiKey": BLOFIN_API_KEY,
        "Request-Time": timestamp,
        "Signature": signature,
        "Content-Type": "application/json"
    }

    try:
        res = requests.post(full_url, headers=headers, data=body_json)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {"error": str(e)}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID or message.author == client.user:
        return

    content = message.content
    symbol_match = re.search(r"([A-Z]+USDT)", content)
    buyzone = re.search(r"BUYZONE\s+([\d.]+)\s*-\s*([\d.]+)", content)
    targets = re.findall(r"(?<!\d)(0\.\d{3,})(?!\d)", content)
    stop = re.search(r"Stop\s+([\d.]+)", content)
    lev_match = re.search(r"Leverage\s*x?(\d+)", content)

    if not all([symbol_match, buyzone, targets, stop, lev_match]):
        print("⚠️ Could not parse trade command.")
        return

    symbol = symbol_match.group(1)
    tp = float(targets[0]) if targets else None
    sl = float(stop.group(1))
    leverage = int(lev_match.group(1))

    price = float(buyzone.group(1))  # Lower bound of buy zone as base
    size = round((TRADE_AMOUNT * leverage) / price, 3)

    response = place_order(symbol, size, leverage, tp, sl)

    if isinstance(response, dict) and response.get("code") == "0":
        await message.channel.send(f"✅ Trade Placed: {symbol} | Size: {size} | TP: {tp} | SL: {sl}")
    else:
        await message.channel.send(f"❌ Trade Failed: {json.dumps(response)}")

client.run(DISCORD_TOKEN)
