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
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE"))

# Discord client setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def sign_blofin_request(api_secret, timestamp, method, path, body=''):
    message = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(api_secret.encode(), message.encode(), hashlib.sha256).hexdigest()

def place_blofin_order(symbol, size, leverage, tp_price, sl_price):
    url_path = "/api/v1/trade/order"
    full_url = f"https://api.blofin.com{url_path}"
    timestamp = str(int(time.time() * 1000))

    body = {
        "instId": f"{symbol.replace('USDT', '')}-USDT",
        "marginMode": "isolated",
        "positionSide": "net",
        "side": "buy",
        "orderType": "market",
        "price": "0",
        "size": str(size),
        "reduceOnly": "false",
        "clientOrderId": str(timestamp),
        "tpTriggerPrice": str(tp_price),
        "tpOrderPrice": "-1",
        "slTriggerPrice": str(sl_price),
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
        response = requests.post(full_url, headers=headers, data=body_json)
        return response.status_code, response.json()
    except Exception as e:
        return 500, {"error": str(e)}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user or message.channel.id != DISCORD_CHANNEL_ID:
        return

    content = message.content
    symbol_match = re.search(r"([A-Z]+USDT)", content)
    targets = re.findall(r"(?<=\n)0\.\d{3,}(?=\n|$)", content)
    stop_match = re.search(r"Stop\s+([\d.]+)", content)
    lev_match = re.search(r"Leverage\s*x?(\d+)", content)

    if not (symbol_match and targets and stop_match and lev_match):
        await message.channel.send("⚠️ Could not parse trade command.")
        return

    symbol = symbol_match.group(1)
    tp_price = float(targets[0])
    sl_price = float(stop_match.group(1))
    leverage = int(lev_match.group(1))

    size = round((TRADE_AMOUNT * leverage) / tp_price, 3)
    code, result = place_blofin_order(symbol, size, leverage, tp_price, sl_price)

    if code == 200 and result.get("code") == "0":
        await message.channel.send(f"✅ Trade placed for {symbol} | Size: {size} | Leverage: {leverage}x")
    else:
        await message.channel.send(f"❌ Trade Failed: {json.dumps(result)}")

client.run(DISCORD_TOKEN)
