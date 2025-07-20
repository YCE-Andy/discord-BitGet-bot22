import os
import re
import hmac
import time
import json
import hashlib
import logging
import requests
import discord
from discord.ext import commands
from decimal import Decimal, ROUND_DOWN

# Environment variables
BITGET_API_KEY = os.getenv("MEXC_API_KEY")
BITGET_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 200))

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

# Constants
BASE_URL = "https://api.bitget.com"
HEADERS = {
    "ACCESS-KEY": BITGET_API_KEY,
    "ACCESS-PASSPHRASE": BITGET_API_PASSPHRASE,
    "Content-Type": "application/json"
}

# Helper: Sign request

def sign_request(timestamp, method, request_path, body=""):
    message = f"{timestamp}{method.upper()}{request_path}{body}"
    mac = hmac.new(BITGET_SECRET_KEY.encode(), message.encode(), hashlib.sha256)
    return mac.hexdigest()

# Helper: Round down to correct precision

def format_quantity(price, quantity):
    precision = Decimal(str(price))
    digits = abs(precision.as_tuple().exponent)
    return str(Decimal(quantity).quantize(Decimal(f"1e-{digits}"), rounding=ROUND_DOWN))

# Place market order

def place_order(symbol, side, size):
    timestamp = str(int(time.time() * 1000))
    endpoint = "/api/v2/mix/order/place-order"
    url = BASE_URL + endpoint
    body = json.dumps({
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": side,
        "orderType": "market",
        "size": str(size),
        "productType": "umcbl"
    })
    signature = sign_request(timestamp, "POST", endpoint, body)
    headers = HEADERS.copy()
    headers.update({
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp
    })
    response = requests.post(url, headers=headers, data=body)
    return response.json()

# Place TP or SL plan order

def place_plan_order(symbol, trigger_price, side, plan_type):
    timestamp = str(int(time.time() * 1000))
    endpoint = "/api/v2/mix/order/place-plan-order"
    url = BASE_URL + endpoint
    body = json.dumps({
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": "0.05",
        "side": side,
        "triggerPrice": str(trigger_price),
        "triggerType": "market_price",
        "executePrice": str(trigger_price),
        "orderType": "limit",
        "planType": plan_type,
        "productType": "umcbl"
    })
    signature = sign_request(timestamp, "POST", endpoint, body)
    headers = HEADERS.copy()
    headers.update({
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp
    })
    response = requests.post(url, headers=headers, data=body)
    return response.json()

# Parse Discord signal

def parse_signal(content):
    try:
        symbol_match = re.search(r"([A-Z]+USDT)", content)
        buyzone = re.search(r"BUYZONE (\d+(\.\d+)?) - (\d+(\.\d+)?)", content)
        targets = re.findall(r"TARGETS\s*([\d\.\s]+)\n", content, re.DOTALL)
        stop = re.search(r"STOP (\d+(\.\d+)?)", content)

        symbol = symbol_match.group(1)
        entry_low = float(buyzone.group(1))
        entry_high = float(buyzone.group(3))
        tp_list = list(map(float, re.findall(r"\d+\.\d+", targets[0]))) if targets else []
        stop_loss = float(stop.group(1))

        return symbol, entry_low, entry_high, tp_list, stop_loss
    except Exception as e:
        logging.error(f"❌ Error extracting trade details: {e}")
        return None, None, None, [], None

# Discord event
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != ALERT_CHANNEL_ID or message.author.bot:
        return

    if "BUYZONE" in message.content:
        await message.channel.send("🟨 Signal received")
        symbol, entry_low, entry_high, tps, sl = parse_signal(message.content)
        if not symbol:
            return

        size = round(TRADE_AMOUNT / ((entry_low + entry_high) / 2), 4)
        order = place_order(symbol, "buy", size)

        if order.get("code") == "00000":
            await message.channel.send(f"✅ Bitget Order Placed: {symbol} x5 [BUY]")
            for i, tp in enumerate(tps[:5]):
                pct = ["50%", "20%", "15%", "10%", "5%"][i]
                tp_result = place_plan_order(symbol, tp, "sell", "profit_plan")
                await message.channel.send(f"📈 TP @{tp}: {tp_result}")

            sl_result = place_plan_order(symbol, sl, "sell", "loss_plan")
            await message.channel.send(f"🛑 SL @{sl}: {sl_result}")
        else:
            await message.channel.send(f"❌ Trade Failed: {order}")

# Run bot
client.run(DISCORD_BOT_TOKEN)
