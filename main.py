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

def sign_blofin_request(api_secret, timestamp, method, path, body=''):
    payload = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

def place_order(symbol, size, leverage, tp_list, sl_price):
    url = "/api/v1/trade/order"
    full_url = f"https://api.blofin.com{url}"
    timestamp = str(int(time.time() * 1000))

    # Market order with optional TP and SL
    order_data = {
        "instId": symbol,
        "marginMode": "isolated",
        "positionSide": "net",
        "side": "buy",
        "orderType": "market",
        "price": "0",  # Not used for market
        "size": str(size),
        "reduceOnly": False,
        "clientOrderId": timestamp
    }

    # Add TP/SL if provided
    if tp_list:
        order_data["tpTriggerPrice"] = str(tp_list[0])
        order_data["tpOrderPrice"] = "-1"  # Market execution
    if sl_price:
        order_data["slTriggerPrice"] = str(sl_price)
        order_data["slOrderPrice"] = "-1"  # Market execution

    body_str = json.dumps(order_data)
    signature = sign_blofin_request(BLOFIN_API_SECRET, timestamp, "POST", url, body_str)

    headers = {
        "ApiKey": BLOFIN_API_KEY,
        "Request-Time": timestamp,
        "Signature": signature,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(full_url, headers=headers, data=body_str)
        if response.status_code != 200:
            return {"error": f"{response.status_code} - {response.text}"}
        return response.json()
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
    targets = re.findall(r"\b0\.\d{3,}\b", content)
    stop_match = re.search(r"Stop\s+([\d.]+)", content)
    lev_match = re.search(r"Leverage\s*x?(\d+)", content)

    if not all([symbol_match, buyzone_match, targets, stop_match, lev_match]):
        await message.channel.send("⚠️ Could not parse trade command.")
        return

    symbol = symbol_match.group(1)
    tp_list = [float(t) for t in targets]
    sl_price = float(stop_match.group(1))
    leverage = int(lev_match.group(1))

    # Use leverage & amount to determine size
    # We assume TRADE_AMOUNT is in USDT
    size = round((TRADE_AMOUNT * leverage) / float(tp_list[0]), 3)  # Estimate from TP1

    result = place_order(symbol, size, leverage, tp_list, sl_price)

    if result.get("code") == "0":
        await message.channel.send(f"✅ Trade Placed: {symbol} with SL and TP")
    elif "error" in result:
        await message.channel.send(f"❌ Trade Failed: {result['error']}")
    else:
        await message.channel.send(f"❌ Trade Failed: {result}")

client.run(DISCORD_TOKEN)
