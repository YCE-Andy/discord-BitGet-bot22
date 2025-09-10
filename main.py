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

# Sign request for BloFin

def sign_blofin_request(api_secret, timestamp, method, path, body=''):
    payload = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

# Place order

def place_order(symbol, size, leverage, tp_price, sl_price):
    url_path = "/api/v1/mix/order/place"
    full_url = f"https://api.blofin.com{url_path}"
    timestamp = str(int(time.time() * 1000))

    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": str(size),
        "price": "",  # Market order
        "side": 1,  # Buy
        "orderType": "market",
        "leverage": leverage,
        "marginMode": "isolated",
        "presetTakeProfitPrice": tp_price,
        "presetStopLossPrice": sl_price
    }

    body_str = json.dumps(body, separators=(',', ':'))
    signature = sign_blofin_request(BLOFIN_API_SECRET, timestamp, "POST", url_path, body_str)

    headers = {
        "ApiKey": BLOFIN_API_KEY,
        "Request-Time": timestamp,
        "Signature": signature,
        "Content-Type": "application/json"
    }

    response = requests.post(full_url, headers=headers, data=body_str)
    print(f"Trade Response: {response.status_code} - {response.text}")
    return response

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
        print("⚠️ Could not parse trade command.")
        return

    symbol = symbol_match.group(1)
    tp_list = [float(t) for t in targets]
    sl_price = stop_match.group(1)
    leverage = int(lev_match.group(1))

    # Calculate size
    # If coin = 0.14 USDT, $500 = 3571 contracts approx
    # We use midpoint of BUYZONE to estimate
    buy_low = float(buyzone_match.group(1))
    buy_high = float(buyzone_match.group(2))
    entry_price = (buy_low + buy_high) / 2
    size = round((TRADE_AMOUNT * leverage) / entry_price, 2)

    response = place_order(symbol, size, leverage, str(tp_list[0]), sl_price)
    try:
        resp_json = response.json()
        if resp_json.get("code") == "00000":
            await message.channel.send(f"✅ Trade Placed: {symbol} | Size: {size} | TP: {tp_list[0]} | SL: {sl_price}")
        else:
            await message.channel.send(f"❌ Trade Failed: {resp_json}")
    except Exception as e:
        await message.channel.send(f"❌ Invalid JSON response from BloFin")
        print(f"Exception: {e}")

client.run(DISCORD_TOKEN)
