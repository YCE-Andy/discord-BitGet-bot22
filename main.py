import os
import discord
import aiohttp
import time
import hmac
import hashlib
import json
from discord.ext import tasks

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

BASE_URL = "https://api.bitget.com"

intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

HEADERS = {
    "Content-Type": "application/json",
    "ACCESS-KEY": BITGET_API_KEY,
    "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
    "locale": "en-US"
}

def sign(message):
    return hmac.new(BITGET_SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()

def get_headers(method, endpoint, body=""):
    timestamp = str(int(time.time() * 1000))
    message = f"{timestamp}{method}{endpoint}{body}"
    signature = sign(message)
    headers = HEADERS.copy()
    headers.update({
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-SIGN": signature
    })
    return headers

async def place_tp_sl(symbol, side, targets, stop_price):
    endpoint = "/api/v2/mix/order/place-plan-order"
    url = BASE_URL + endpoint
    product_type = "umcbl"
    margin_mode = "isolated"
    trigger_type = "market_price"

    async with aiohttp.ClientSession() as session:
        for tp in targets:
            body = {
                "symbol": symbol,
                "marginMode": margin_mode,
                "planType": "profit_plan",
                "triggerPrice": str(tp),
                "triggerType": trigger_type,
                "orderType": "limit",
                "side": "sell" if side == "buy" else "buy",
                "size": "0.05",  # Adjusted based on live trades
                "price": str(tp),
                "executePrice": str(tp),
                "productType": product_type
            }
            body_str = json.dumps(body)
            headers = get_headers("POST", endpoint, body_str)
            async with session.post(url, data=body_str, headers=headers) as resp:
                rdata = await resp.json()
                print(f"TP @ {tp}: {rdata}")

        # Stop-loss
        body = {
            "symbol": symbol,
            "marginMode": margin_mode,
            "planType": "loss_plan",
            "triggerPrice": str(stop_price),
            "triggerType": trigger_type,
            "orderType": "limit",
            "side": "sell" if side == "buy" else "buy",
            "size": "0.05",
            "price": str(stop_price),
            "executePrice": str(stop_price),
            "productType": product_type
        }
        body_str = json.dumps(body)
        headers = get_headers("POST", endpoint, body_str)
        async with session.post(url, data=body_str, headers=headers) as resp:
            rdata = await resp.json()
            print(f"SL @ {stop_price}: {rdata}")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.channel.id != ALERT_CHANNEL_ID or message.author == client.user:
        return

    content = message.content
    if not any(keyword in content.upper() for keyword in ["BUYZONE", "SELLZONE"]):
        return

    lines = content.splitlines()
    symbol = lines[0].strip().replace(" ", "").upper()
    side = "buy" if "BUYZONE" in content.upper() else "sell"

    buyzone = next((l for l in lines if "BUYZONE" in l.upper() or "SELLZONE" in l.upper()), None)
    stop = next((l for l in lines if "STOP" in l.upper()), None)
    targets_index = next(i for i, l in enumerate(lines) if "TARGETS" in l.upper())
    targets = [float(l.strip()) for l in lines[targets_index+1:] if l.strip() and not l.upper().startswith("STOP")]

    stop_price = float(stop.split()[-1]) if stop else None

    await message.channel.send(f"✅ Bitget Order Placed: {symbol} x5 [{'BUY' if side == 'buy' else 'SELL'}]")
    await place_tp_sl(symbol, side, targets[:5], stop_price)

client.run(DISCORD_BOT_TOKEN)
