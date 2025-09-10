from dotenv import load_dotenv
import os
import discord
import re
import time
import hmac
import hashlib
import requests
import json

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
BLOFIN_API_KEY = os.getenv("BLOFIN_API_KEY")
BLOFIN_API_SECRET = os.getenv("BLOFIN_API_SECRET")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT"))  # in USDT

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Signature function for BloFin

def sign_blofin_request(api_secret, timestamp, method, path, body=''):
    payload = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

# Place a market order on BloFin

def place_order(symbol, size, leverage, tp_price, sl_price):
    url_path = "/api/v1/trade/order"
    full_url = f"https://api.blofin.com{url_path}"
    timestamp = str(int(time.time() * 1000))

    body = {
        "instId": symbol,
        "marginMode": "isolated",
        "positionSide": "net",
        "side": "buy",
        "orderType": "market",
        "price": "",  # Not used for market orders
        "size": str(size),
        "reduceOnly": False,
        "tpTriggerPrice": str(tp_price),
        "tpOrderPrice": "-1",
        "slTriggerPrice": str(sl_price),
        "slOrderPrice": "-1",
        "clientOrderId": str(timestamp)
    }

    body_str = json.dumps(body)
    signature = sign_blofin_request(BLOFIN_API_SECRET, timestamp, "POST", url_path, body_str)

    headers = {
        "ApiKey": BLOFIN_API_KEY,
        "Request-Time": timestamp,
        "Signature": signature,
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(full_url, headers=headers, data=body_str)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# Parse command message from Discord

def parse_trade_command(content):
    try:
        symbol_match = re.search(r"([A-Z]+USDT)", content)
        targets = re.findall(r"(?<=\n|\s)0\.\d{3,}(?=\n|\s|$)", content)
        stop_match = re.search(r"STOP\s+([\d.]+)", content, re.IGNORECASE)
        leverage_match = re.search(r"LEVERAGE\s*x?(\d+)", content, re.IGNORECASE)

        if not (symbol_match and targets and stop_match and leverage_match):
            return None

        symbol = symbol_match.group(1)
        tp_price = float(targets[0])  # Use first TP
        sl_price = float(stop_match.group(1))
        leverage = int(leverage_match.group(1))

        size = round((TRADE_AMOUNT * leverage) / tp_price, 3)

        return {
            "symbol": symbol,
            "tp": tp_price,
            "sl": sl_price,
            "lev": leverage,
            "size": size
        }
    except:
        return None

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID or message.author == client.user:
        return

    trade_data = parse_trade_command(message.content)

    if not trade_data:
        await message.channel.send("⚠️ Could not parse trade command.")
        return

    result = place_order(
        trade_data["symbol"],
        trade_data["size"],
        trade_data["lev"],
        trade_data["tp"],
        trade_data["sl"]
    )

    if result.get("code") == "0":
        await message.channel.send(f"✅ Trade Placed: {trade_data['symbol']} TP: {trade_data['tp']} SL: {trade_data['sl']}")
    else:
        await message.channel.send(f"❌ Trade Failed: {result}")

client.run(DISCORD_TOKEN)
