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
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT"))  # e.g. 500
LEVERAGE = int(os.getenv("LEVERAGE"))  # e.g. 10
FALLBACK_PRICE = 1.0  # Used to calculate size if no price is fetched

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def sign_blofin_request(api_secret, timestamp, method, path, body=''):
    payload = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

def place_order(symbol, side, size, leverage, tp_price, sl_price):
    url = "/api/v1/trade/order"
    full_url = f"https://api.blofin.com{url}"
    timestamp = str(int(time.time() * 1000))

    body = {
        "symbol": symbol,
        "price": "",  # market order
        "vol": size,
        "side": side,  # 1 = buy
        "type": 1,     # 1 = market order
        "open_type": 1,  # isolated margin
        "position_id": 0,
        "leverage": leverage,
        "external_oid": str(timestamp),
        "stop_loss_price": sl_price,
        "take_profit_price": tp_price,
        "position_mode": 1,
        "reduce_only": False
    }

    body_str = json.dumps(body)
    signature = sign_blofin_request(BLOFIN_API_SECRET, timestamp, "POST", url, body_str)

    headers = {
        "ApiKey": BLOFIN_API_KEY,
        "Request-Time": timestamp,
        "Signature": signature,
        "Content-Type": "application/json"
    }

    r = requests.post(full_url, headers=headers, data=body_str)
    print(f"📤 Trade response: {r.status_code} - {r.text}")
    return r.json()

@client.event
async def on_ready():
    print(f"✅ Bot connected as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID or message.author == client.user:
        return

    content = message.content
    print(f"📩 Message received: {content}")

    symbol_match = re.search(r"([A-Z]+USDT)", content)
    buyzone_match = re.search(r"BUYZONE\s+([\d.]+)\s*-\s*([\d.]+)", content)
    targets = re.findall(r"\b0\.\d{3,}\b", content)
    stop_match = re.search(r"Stop\s+([\d.]+)", content)
    lev_match = re.search(r"Leverage\s*x?(\d+)", content)

    if not all([symbol_match, buyzone_match, targets, stop_match, lev_match]):
        await message.channel.send("⚠️ Incomplete message format — skipping.")
        return

    symbol = symbol_match.group(1)
    tp_price = float(targets[0]) if targets else None
    sl_price = float(stop_match.group(1))
    leverage = int(lev_match.group(1))

    # ✅ No market price check — just use fallback to calculate position size
    size = round((TRADE_AMOUNT * leverage) / FALLBACK_PRICE, 3)

    order = place_order(symbol, 1, size, leverage, tp_price, sl_price)
    if order.get("code") == "0":
        await message.channel.send(f"✅ Trade Placed: {symbol} | Size: {size} | Lev: x{leverage}")
    else:
        await message.channel.send(f"❌ Trade Failed: {order}")

client.run(DISCORD_TOKEN)
