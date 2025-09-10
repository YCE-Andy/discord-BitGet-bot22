import os
import time
import uuid
import hmac
import hashlib
import base64
import json
import requests
import discord
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

BLOFIN_API_KEY = os.getenv("BLOFIN_API_KEY")
BLOFIN_API_SECRET = os.getenv("BLOFIN_API_SECRET")
BLOFIN_API_PASSPHRASE = os.getenv("BLOFIN_API_PASSPHRASE")

TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT"))
LEVERAGE = int(os.getenv("LEVERAGE"))

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def sign_blofin_request(secret, timestamp, nonce, method, path, body=''):
    prehash = f"{path}{method}{timestamp}{nonce}{body}"
    hmac_digest = hmac.new(secret.encode(), prehash.encode(), hashlib.sha256).hexdigest()
    signature = base64.b64encode(hmac_digest.encode()).decode()
    return signature

def place_order(symbol, side, size, leverage, tp_price, sl_price):
    path = "/api/v1/trade/order"
    url = f"https://openapi.blofin.com{path}"
    timestamp = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())

    body = {
        "symbol": symbol,
        "price": "",
        "vol": size,
        "side": side,
        "type": 1,
        "open_type": 1,
        "position_id": 0,
        "leverage": leverage,
        "external_oid": timestamp,
        "stop_loss_price": sl_price,
        "take_profit_price": tp_price,
        "position_mode": 1,
        "reduce_only": False
    }

    body_json = json.dumps(body)
    signature = sign_blofin_request(BLOFIN_API_SECRET, timestamp, nonce, "POST", path, body_json)

    headers = {
        "ACCESS-KEY": BLOFIN_API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-NONCE": nonce,
        "ACCESS-PASSPHRASE": BLOFIN_API_PASSPHRASE,
        "Content-Type": "application/json"
    }

    r = requests.post(url, headers=headers, data=body_json)
    print(f"🚨 Raw response: {r.status_code} - {r.text}")
    try:
        return r.json()
    except Exception as e:
        return {"error": f"Invalid JSON: {e}\nRaw: {r.text}"}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID or message.author == client.user:
        return

    content = message.content
    symbol_match = re.search(r"([A-Z]+USDT)", content)
    targets = re.findall(r"\b0\.\d{3,}\b", content)
    stop_match = re.search(r"Stop\s+([\d.]+)", content)
    lev_match = re.search(r"Leverage\s*x?(\d+)", content)

    if not (symbol_match and targets and stop_match and lev_match):
        await message.channel.send("⚠️ Could not parse trade command.")
        return

    symbol = symbol_match.group(1)
    tp = float(targets[0])
    sl = float(stop_match.group(1))
    leverage = int(lev_match.group(1))

    size = round((TRADE_AMOUNT * leverage) / tp, 3)
    result = place_order(symbol, 1, size, leverage, tp, sl)

    if result.get("code") == "0":
        await message.channel.send(f"✅ Trade Placed: {symbol} | TP: {tp} | SL: {sl}")
    else:
        await message.channel.send(f"❌ Trade Failed: {result}")

client.run(DISCORD_TOKEN)
