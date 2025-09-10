import os
import json
import time
import hmac
import hashlib
import requests
import discord
import re
from dotenv import load_dotenv

# Load env vars
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
BLOFIN_API_KEY = os.getenv("BLOFIN_API_KEY")
BLOFIN_API_SECRET = os.getenv("BLOFIN_API_SECRET")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT"))  # e.g. 500
LEVERAGE = int(os.getenv("LEVERAGE"))  # e.g. 10

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def sign_blofin_request(secret, timestamp, method, path, body=''):
    msg = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

def place_order(symbol, side, size, leverage, tp, sl):
    url_path = "/api/v1/trade/order"
    url = f"https://api.blofin.com{url_path}"
    timestamp = str(int(time.time() * 1000))

    body = {
        "symbol": symbol,
        "price": "",               # Market order
        "vol": size,
        "side": side,              # 1 = buy
        "type": 1,                 # 1 = market
        "open_type": 1,            # Isolated margin
        "position_id": 0,
        "leverage": leverage,
        "external_oid": timestamp,
        "stop_loss_price": sl,
        "take_profit_price": tp,
        "position_mode": 1,
        "reduce_only": False
    }

    body_json = json.dumps(body)
    signature = sign_blofin_request(BLOFIN_API_SECRET, timestamp, "POST", url_path, body_json)

    headers = {
        "ApiKey": BLOFIN_API_KEY,
        "Request-Time": timestamp,
        "Signature": signature,
        "Content-Type": "application/json"
    }

    r = requests.post(url, headers=headers, data=body_json)
    try:
        return r.json()
    except:
        return {"error": "❌ Invalid JSON response from BloFin"}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user or message.channel.id != DISCORD_CHANNEL_ID:
        return

    content = message.content
    symbol_match = re.search(r"([A-Z]+USDT)", content)
    targets = re.findall(r"\b0\.\d{3,}\b", content)
    stop_match = re.search(r"Stop\s+([\d.]+)", content)
    lev_match = re.search(r"Leverage\s*x?(\d+)", content)

    if not (symbol_match and targets and stop_match and lev_match):
        await message.channel.send("⚠️ Could not parse trade signal. Please check the format.")
        return

    symbol = symbol_match.group(1)
    tp = float(targets[0]) if targets else ""
    sl = float(stop_match.group(1))
    leverage = int(lev_match.group(1))

    size = round((TRADE_AMOUNT * leverage) / tp, 3) if tp else 1

    result = place_order(symbol, 1, size, leverage, tp, sl)

    if "error" in result:
        await message.channel.send(result["error"])
    elif result.get("code") == "0":
        await message.channel.send(f"✅ Trade Placed: {symbol}\n🎯 TP: {tp} | 🛑 SL: {sl}")
    else:
        await message.channel.send(f"❌ Trade Failed: {result}")

client.run(DISCORD_TOKEN)
