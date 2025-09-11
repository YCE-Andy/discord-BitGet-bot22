import os
import time
import hmac
import hashlib
import base64
import json
import aiohttp
import asyncio
import discord
from discord.ext import commands

# ✅ Load API credentials from environment (corrected for BloFin)
API_KEY = os.getenv("BLOFIN_API_KEY")
API_SECRET = os.getenv("BLOFIN_API_SECRET")
PASSPHRASE = os.getenv("BLOFIN_API_PASSPHRASE")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
LEVERAGE = int(os.getenv("LEVERAGE"))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT"))

API_URL = "https://api.blofin.com"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ✅ Helper to create BloFin API headers
def generate_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    prehash = timestamp + method + path + body
    signature = base64.b64encode(
        hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).digest()
    ).decode()

    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# ✅ Execute a market order on BloFin
async def place_order(symbol, side, tp=None, sl=None):
    try:
        # Convert symbol to BloFin format (e.g., AIUSDT → AI-USDT)
        instId = symbol.upper().replace("USDT", "-USDT")

        # Get market price
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/api/v1/market/ticker?instId={instId}") as resp:
                ticker = await resp.json()
        mark_price = float(ticker['data']['markPrice'])

        size = round((TRADE_AMOUNT * LEVERAGE) / mark_price, 4)

        payload = {
            "instId": instId,
            "marginMode": "isolated",
            "positionSide": "net",
            "side": side,
            "orderType": "market",
            "size": str(size)
        }

        if tp:
            payload["tpTriggerPrice"] = str(tp)
            payload["tpOrderPrice"] = "-1"
        if sl:
            payload["slTriggerPrice"] = str(sl)
            payload["slOrderPrice"] = "-1"

        body = json.dumps(payload)
        headers = generate_headers("POST", "/api/v1/trade/order", body)

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_URL}/api/v1/trade/order", data=body, headers=headers) as resp:
                res = await resp.text()
                try:
                    json_res = json.loads(res)
                except json.JSONDecodeError:
                    await notify(f"❌ Trade Failed: Invalid JSON: {res}")
                    return

                if json_res.get("code") == "0":
                    await notify(f"✅ Trade executed: {symbol}, Side: {side}, Size: {size}")
                else:
                    await notify(f"❌ Trade Failed: {json_res}")

    except Exception as e:
        await notify(f"❌ Exception: {str(e)}")

# ✅ Notify in Discord
async def notify(message):
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(message)

# ✅ Parse trade signal from message content
def parse_signal(content):
    lines = content.strip().splitlines()
    symbol, targets, stop, lev = None, [], None, None

    for line in lines:
        if "TARGETS" in line.upper():
            targets = [float(x) for x in line.upper().replace("TARGETS", "").strip().split()]
        elif "STOP" in line.upper():
            stop = float(line.upper().replace("STOP", "").strip())
        elif "LEVERAGE" in line.upper():
            lev = line.upper().replace("LEVERAGE", "").replace("X", "").strip()
        elif line.strip().isalpha() or line.strip().endswith("USDT"):
            symbol = line.strip().upper()

    if symbol and targets and stop:
        return symbol, targets[0], stop
    return None, None, None

# ✅ Bot event
@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user or message.channel.id != DISCORD_CHANNEL_ID:
        return

    symbol, tp, sl = parse_signal(message.content)
    if not symbol:
        await notify("⚠️ Could not parse trade command.")
        return

    await place_order(symbol, "buy", tp, sl)

bot.run(DISCORD_TOKEN)
