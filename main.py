import os
import discord
import re
import hmac
import hashlib
import time
import requests
import json

# Load environment variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")

API_BASE = "https://contract.mexc.com"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def sign(params, secret):
    sorted_params = sorted(params.items())
    encoded = "&".join([f"{k}={v}" for k, v in sorted_params])
    return hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()

def place_futures_order(symbol, side, quantity, leverage):
    path = "/api/v1/private/order/submit"
    url = API_BASE + path
    timestamp = int(time.time() * 1000)

    order_params = {
        "apiKey": MEXC_API_KEY,
        "req_time": timestamp,
        "market": symbol,
        "price": 0,
        "vol": quantity,
        "leverage": leverage,
        "side": 1 if side == "buy" else 2,
        "type": 1,  # 1=market order
        "open_type": 1,  # isolated
        "position_id": 0,
        "external_oid": str(timestamp),
        "stop_loss_price": 0,
        "take_profit_price": 0,
        "position_mode": 1
    }

    order_params["sign"] = sign(order_params, MEXC_SECRET_KEY)
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, data=json.dumps(order_params), headers=headers)
    return response.json()

@client.event
async def on_ready():
    print(f"[READY] Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != RELAY_CHANNEL_ID or message.author == client.user:
        return

    content = message.content
    match = re.search(r"([A-Z]+USDT)", content)
    if not match:
        return

    base_symbol = match.group(1)
    symbol = f"{base_symbol[:-4]}_USDT"

    buyzone = re.findall(r"BUYZONE\s+([\d.]+)\s*-\s*([\d.]+)", content)
    targets = re.findall(r"TARGETS\s+([\d.\s]+)", content)
    leverage_match = re.search(r"LEVERAGE\s*x?(\d+)", content)

    if not buyzone or not leverage_match:
        return

    entry_low = float(buyzone[0][0])
    entry_high = float(buyzone[0][1])
    entry = (entry_low + entry_high) / 2
    leverage = int(leverage_match.group(1))

    try:
        notional = 200
        qty = round(notional / entry, 3)

        await message.channel.send(f"🚀 Placing market order: BUY {symbol} ~{qty} @ {entry} with x{leverage}")
        result = place_futures_order(symbol, "buy", qty, leverage)

        if result.get("success"):
            await message.channel.send(f"✅ Trade success: {symbol} qty={qty} x{leverage}")
        else:
            error_msg = result.get("message", "Unknown error")
            await message.channel.send(f"[ERROR] Trade failed: {error_msg}")

    except Exception as e:
        await message.channel.send(f"[ERROR] Exception: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
