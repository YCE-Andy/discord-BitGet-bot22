import os
import discord
import requests
import time
import hmac
import hashlib
import json
from decimal import Decimal
from discord.ext import commands

# === CONFIG ===
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
BLOFIN_API_KEY = os.getenv("BLOFIN_API_KEY")
BLOFIN_SECRET_KEY = os.getenv("BLOFIN_SECRET_KEY")
BLOFIN_PASSPHRASE = os.getenv("BLOFIN_PASSPHRASE")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 100))  # Base USDT amount
BLOFIN_BASE_URL = "https://api.blofin.com"

# === HEADERS GENERATOR ===
def generate_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    body_str = json.dumps(body) if isinstance(body, dict) else body
    prehash = f"{timestamp}{method.upper()}{path}{body_str}"
    signature = hmac.new(
        BLOFIN_SECRET_KEY.encode(), prehash.encode(), hashlib.sha256
    ).hexdigest()
    return {
        "ACCESS-KEY": BLOFIN_API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BLOFIN_PASSPHRASE,
        "Content-Type": "application/json",
    }

# === PLACE TRADE ===
def place_trade(symbol, side, leverage, tp=None, sl=None):
    try:
        # Fetch latest market price
        market_res = requests.get(f"{BLOFIN_BASE_URL}/api/v1/market/ticker?instId={symbol}-PERP")
        market_data = market_res.json()
        price = float(market_data["data"]["last"])
        size = round((TRADE_AMOUNT * leverage) / price, 4)

        body = {
            "instId": f"{symbol}-PERP",
            "marginMode": "isolated",
            "positionSide": "net",
            "side": side.lower(),
            "orderType": "market",
            "size": str(size)
        }

        if tp:
            body["tpTriggerPrice"] = str(tp)
            body["tpOrderPrice"] = "-1"
        if sl:
            body["slTriggerPrice"] = str(sl)
            body["slOrderPrice"] = "-1"

        headers = generate_headers("POST", "/api/v1/trade/order", body)
        response = requests.post(f"{BLOFIN_BASE_URL}/api/v1/trade/order", headers=headers, data=json.dumps(body))

        if response.status_code == 200:
            return f"✅ Trade placed for {symbol} | Side: {side.upper()} | Size: {size} @ {price}"
        else:
            return f"❌ Trade Failed: {response.text}"
    except Exception as e:
        return f"❌ Exception: {str(e)}"

# === PARSE COMMAND ===
def parse_trade_command(message):
    try:
        lines = message.strip().upper().splitlines()
        symbol = ""
        targets = []
        stop = None
        leverage = 1

        for line in lines:
            if line.startswith("TARGETS"):
                targets = list(map(float, line.replace("TARGETS", "").split()))
            elif line.startswith("STOP"):
                stop = float(line.replace("STOP", "").strip())
            elif line.startswith("LEVERAGE"):
                leverage = int(line.replace("LEVERAGE", "").replace("X", "").strip())
            elif line and not line.startswith(("TARGETS", "STOP", "LEVERAGE")):
                symbol = line.replace("/USDT", "").replace("-PERP", "").strip()

        if not symbol or not targets or not stop or not leverage:
            return None, "⚠️ Could not parse trade command."

        return {
            "symbol": symbol,
            "targets": targets,
            "stop": stop,
            "leverage": leverage
        }, None
    except Exception as e:
        return None, f"⚠️ Parse error: {str(e)}"

# === BOT SETUP ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.channel.id != CHANNEL_ID or message.author == bot.user:
        return

    parsed, error = parse_trade_command(message.content)
    if error:
        await message.channel.send(error)
        return

    symbol = parsed["symbol"]
    leverage = parsed["leverage"]
    tp = parsed["targets"][0] if parsed["targets"] else None
    sl = parsed["stop"]
    side = "buy"  # Default to long, could add parsing for SELL later

    result = place_trade(symbol, side, leverage, tp, sl)
    await message.channel.send(result)

bot.run(DISCORD_TOKEN)
