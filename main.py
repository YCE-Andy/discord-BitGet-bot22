import os
import time
import hmac
import hashlib
import base64
import json
import aiohttp
import discord
from discord.ext import commands
from urllib.parse import urlencode

# ✅ Load correct BloFin environment variables
API_KEY = os.getenv("BLOFIN_API_KEY")
API_SECRET = os.getenv("BLOFIN_API_SECRET")
PASSPHRASE = os.getenv("BLOFIN_API_PASSPHRASE")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
LEVERAGE = int(os.getenv("LEVERAGE", 5))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 50))

HEADERS = {
    "Content-Type": "application/json",
    "X-BLOFIN-KEY": API_KEY,
    "X-BLOFIN-PASSPHRASE": PASSPHRASE,
}

BASE_URL = "https://api.blofin.com"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ✅ Signature generation function
def generate_signature(timestamp, method, request_path, body=""):
    prehash = f"{timestamp}{method}{request_path}{body}"
    signature = hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).digest()
    return base64.b64encode(signature).decode()

# ✅ Place trade
async def place_trade(symbol, targets, stop, leverage):
    try:
        instId = symbol.upper()  # e.g., "AIUSDT"
        side = "buy"
        margin_mode = "isolated"
        position_mode = "net"
        order_type = "market"

        # Use price of TP1 to calculate trade size
        entry_price = float(targets[0])
        size = round((TRADE_AMOUNT * leverage) / entry_price, 3)

        timestamp = str(int(time.time() * 1000))
        endpoint = "/api/v1/trade/order"
        url = BASE_URL + endpoint

        payload = {
            "instId": instId,
            "marginMode": margin_mode,
            "positionSide": position_mode,
            "side": side,
            "orderType": order_type,
            "size": str(size),
            "tpTriggerPrice": str(targets[-1]),
            "tpOrderPrice": "-1",
            "slTriggerPrice": str(stop),
            "slOrderPrice": "-1"
        }

        body = json.dumps(payload)
        signature = generate_signature(timestamp, "POST", endpoint, body)

        headers = HEADERS.copy()
        headers.update({
            "X-BLOFIN-TIMESTAMP": timestamp,
            "X-BLOFIN-SIGN": signature,
        })

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=body) as resp:
                res_text = await resp.text()
                if resp.status == 200:
                    data = await resp.json()
                    return f"✅ Trade placed: {data}"
                else:
                    return f"❌ Trade Failed: {res_text}"

    except Exception as e:
        return f"❌ Exception: {str(e)}"

# ✅ Parse trade message
def parse_trade_message(msg):
    try:
        lines = msg.upper().splitlines()
        symbol = None
        targets = []
        stop = None
        leverage = LEVERAGE

        for line in lines:
            if line.strip().endswith("USDT"):
                symbol = line.strip()
            elif line.startswith("TARGET"):
                targets = [x for x in line.split() if x.replace(".", "", 1).isdigit()]
            elif line.startswith("STOP"):
                parts = line.split()
                stop = parts[-1] if len(parts) > 1 else None
            elif line.startswith("LEVERAGE"):
                parts = line.split("X")
                leverage = int(parts[-1]) if len(parts) > 1 else LEVERAGE

        if symbol and targets and stop:
            return symbol, targets, stop, leverage
        else:
            return None
    except:
        return None

# ✅ Discord bot listener
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID or message.author == bot.user:
        return

    parsed = parse_trade_message(message.content)
    if not parsed:
        await message.channel.send("⚠️ Could not parse trade command.")
        return

    symbol, targets, stop, lev = parsed
    response = await place_trade(symbol, targets, stop, lev)
    await message.channel.send(response)

bot.run(DISCORD_TOKEN)
