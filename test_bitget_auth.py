import os
import time
import hmac
import hashlib
import requests
import discord
import re
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()

# Load environment variables
API_KEY = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 500))
LEVERAGE = int(os.getenv("LEVERAGE", 10))
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# Discord bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Parse trade signal message
def parse_signal(message):
    try:
        symbol = re.search(r"^([A-Z]+USDT)", message).group(1)
        buyzone = re.search(r"BUYZONE\s+(\d+\.\d+)\s*-\s*(\d+\.\d+)", message)
        stop = re.search(r"Stop\s+(\d+\.\d+)", message)
        
        if symbol and buyzone and stop:
            return {
                "symbol": symbol.upper(),
                "buy_low": float(buyzone.group(1)),
                "buy_high": float(buyzone.group(2)),
                "stop": float(stop.group(1))
            }
    except:
        pass
    return None

# BloFin signature generator
def sign_request(secret, timestamp, method, path, query="", body=""):
    prehash = f"{timestamp}{method}{path}{query}{body}"
    return hmac.new(secret.encode(), prehash.encode(), hashlib.sha256).hexdigest()

# Fetch current market price for symbol
def get_market_price(symbol):
    url = f"https://api.blofin.com/api/v1/market/ticker?symbol={symbol}"
    res = requests.get(url)
    data = res.json()
    return float(data['data']['close']) if 'data' in data else None

# Place market order

def place_blofin_order(symbol, size, leverage):
    ts = str(int(time.time() * 1000))
    path = "/api/v1/order/place"
    body = {
        "symbol": symbol,
        "price": "",  # market order
        "vol": size,
        "side": 1,  # 1 = Buy
        "type": 1,  # 1 = Market
        "open_type": 1,  # 1 = Isolated
        "position_id": 0,
        "leverage": leverage,
        "external_oid": f"discord-{ts}"
    }

    signature = sign_request(SECRET_KEY, ts, "POST", path, body=str(body).replace("'", '"'))

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

    res = requests.post(f"https://api.blofin.com{path}", json=body, headers=headers)
    return res.json()

@bot.event
async def on_ready():
    print(f"✅ Bot connected as {bot.user}")

@bot.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID or message.author.bot:
        return

    trade = parse_signal(message.content)
    if trade:
        symbol = trade['symbol']
        price = get_market_price(symbol)

        if price and trade['buy_low'] <= price <= trade['buy_high']:
            position_value = TRADE_AMOUNT
            res = place_blofin_order(symbol, position_value, LEVERAGE)
            await message.channel.send(f"🚀 Trade placed for {symbol} at {price} | Response: {res}")
        else:
            await message.channel.send(f"⏳ {symbol} price {price} not in buy zone {trade['buy_low']} - {trade['buy_high']}")

bot.run(DISCORD_TOKEN)
