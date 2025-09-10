import os
import time
import hmac
import hashlib
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
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT"))
LEVERAGE = int(os.getenv("LEVERAGE"))

# Discord setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def sign_blofin_request(api_secret, timestamp, method, path, body=''):
    payload = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

def place_market_order(symbol, side, size, tp=None, sl=None):
    url_path = "/api/v1/trade/order"
    full_url = f"https://api.blofin.com{url_path}"
    timestamp = str(int(time.time() * 1000))

    body = {
        "instId": symbol,
        "marginMode": "isolated",
        "positionSide": "net",
        "side": "buy" if side == 1 else "sell",
        "orderType": "market",
        "size": str(size),
        "reduceOnly": False
    }

    # Optional TP/SL
    if tp:
        body["tpTriggerPrice"] = str(tp)
        body["tpOrderPrice"] = "-1"
    if sl:
        body["slTriggerPrice"] = str(sl)
        body["slOrderPrice"] = "-1"

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
        print(f"🔁 Response: {res.status_code} - {res.text}")
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
    buyzone_match = re.search(r"BUYZONE\s+([\d.]+)\s*-\s*([\d.]+)", content)
    targets = re.findall(r"(?<=\n|\s|^)0\.\d{2,}(?=\n|\s|$)", content)
    stop_match = re.search(r"Stop\s+([\d.]+)", content)
    lev_match = re.search(r"Leverage\s*x?(\d+)", content)

    if not all([symbol_match, buyzone_match, targets, stop_match, lev_match]):
        await message.channel.send("⚠️ Could not parse trade command.")
        return

    symbol = symbol_match.group(1)
    tp_list = [float(t) for t in targets]
    sl_price = float(stop_match.group(1))
    leverage = int(lev_match.group(1))

    # Calculate position size (contracts)
    entry_price = tp_list[0]  # First TP used to approximate entry price
    size = round((TRADE_AMOUNT * leverage) / entry_price, 3)

    order = place_market_order(symbol, 1, size, tp=tp_list[0], sl=sl_price)

    if order.get("code") == "0":
        await message.channel.send(f"✅ Trade Placed: {symbol} | Size: {size} | TP: {tp_list[0]} | SL: {sl_price}")
    elif order.get("error"):
        await message.channel.send(f"❌ Trade Failed: {order['error']}")
    else:
        await message.channel.send(f"❌ Trade Failed: {order}")

client.run(DISCORD_TOKEN)
