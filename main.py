import discord
import re
import time
import hmac
import hashlib
import requests
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

API_BASE = "https://contract.mexc.com"

def generate_signature(api_key, secret_key, req_time, sign_params):
    sign_params['api_key'] = api_key
    sign_params['req_time'] = str(req_time)
    sign_params = dict(sorted(sign_params.items()))
    message = '&'.join([f"{k}={v}" for k, v in sign_params.items()])
    signature = hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

def place_futures_order(symbol, side, volume, leverage):
    req_time = int(time.time() * 1000)
    order_params = {
        "symbol": symbol,
        "price": 0,
        "vol": volume,
        "leverage": leverage,
        "side": 1 if side == 'buy' else 2,
        "type": 1,  # 1 = market order
        "open_type": 1,  # 1 = isolated
        "position_id": 0,
        "external_oid": str(uuid.uuid4()),
        "stop_loss_price": 0,
        "take_profit_price": 0
    }
    signature = generate_signature(MEXC_API_KEY, MEXC_SECRET_KEY, req_time, order_params)
    order_params['api_key'] = MEXC_API_KEY
    order_params['req_time'] = req_time
    order_params['sign'] = signature

    response = requests.post(f"{API_BASE}/api/v1/private/order/submit", data=order_params)
    return response.json()

@client.event
async def on_ready():
    print(f"[READY] Bot is online as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != RELAY_CHANNEL_ID or message.author == client.user:
        return

    content = message.content
    if "BUYZONE" not in content.upper():
        return

    match = re.search(r"(\w+USDT)", content)
    if not match:
        await message.channel.send("[ERROR] Could not parse symbol.")
        return

    base = match.group(1).replace("/", "").upper()
    symbol = f"{base}_USDT"

    try:
        buyzone = re.findall(r"BUYZONE\s+([0-9.]+)\s*-\s*([0-9.]+)", content.upper())[0]
        entry_price = float(buyzone[0])
        leverage_match = re.search(r"LEVERAGE\s*[xX]?(\d+)", content.upper())
        leverage = int(leverage_match.group(1)) if leverage_match else 5
        qty = round(100 / entry_price, 4)  # $100 trade value

        await message.channel.send(f"\ud83d\ude80 Placing market order: BUY {qty} {symbol} with x{leverage}")
        response = place_futures_order(symbol, "buy", qty, leverage)

        if response.get("success"):
            await message.channel.send(f"[SUCCESS] Trade executed: BUY {qty} {symbol} with x{leverage} leverage")
        else:
            error_msg = response.get("message", str(response))
            await message.channel.send(f"[ERROR] Trade failed: {error_msg}")

    except Exception as e:
        await message.channel.send(f"[ERROR] Exception: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
