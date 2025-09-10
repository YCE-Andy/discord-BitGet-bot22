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
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT"))  # $500
LEVERAGE = int(os.getenv("LEVERAGE"))  # x10

# Discord client setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Signature function for BloFin API
def sign_blofin_request(api_secret, timestamp, method, path, body=''):
    payload = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

# Fetch market price from BloFin
def get_market_price(symbol):
    url = f"https://api.blofin.com/api/v1/market/ticker?symbol={symbol}"
    try:
        response = requests.get(url)
        data = response.json()
        return float(data["data"]["lastPrice"])
    except:
        return None

# Place market order on BloFin
def place_order(symbol, side, size, leverage, tp_list, sl_price):
    url = "/api/v1/trade/order"
    full_url = f"https://api.blofin.com{url}"
    timestamp = str(int(time.time() * 1000))

    body = {
        "symbol": symbol,
        "price": "",
        "vol": size,
        "side": side,  # 1 = Buy, 2 = Sell
        "type": 1,     # 1 = Market
        "open_type": 1,  # Isolated
        "position_id": 0,
        "leverage": leverage,
        "external_oid": str(timestamp),
        "stop_loss_price": sl_price,
        "take_profit_price": tp_list[0] if tp_list else "",
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
    print(f"📤 Sent trade request: {body}")
    print(f"📥 BloFin response: {r.status_code} - {r.text}")
    return r.json()

# When bot is ready
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

# On new message in Discord
@client.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID or message.author == client.user:
        return

    content = message.content

    symbol_match = re.search(r"([A-Z]+USDT)", content)
    buyzone_match = re.search(r"BUYZONE\s+([\d.]+)\s*-\s*([\d.]+)", content)
    targets = re.findall(r"\b0\.\d{3,}\b", content)
    stop_match = re.search(r"Stop\s+([\d.]+)", content)
    lev_match = re.search(r"Leverage\s*x?(\d+)", content)

    if not all([symbol_match, buyzone_match, targets, stop_match, lev_match]):
        print("⚠️ Missing or invalid data in message — skipping.")
        return

    symbol = symbol_match.group(1)
    buy_low = float(buyzone_match.group(1))
    buy_high = float(buyzone_match.group(2))
    tp_list = [float(t) for t in targets if float(t) > buy_high]
    sl_price = float(stop_match.group(1))
    leverage = int(lev_match.group(1))

    market_price = get_market_price(symbol)

    if market_price is None:
        await message.channel.send(f"❌ Couldn't fetch market price for {symbol}")
        return

    print(f"🔎 {symbol} market price: {market_price}")
    print(f"📈 BUYZONE: {buy_low} - {buy_high}")

    if buy_low <= market_price <= buy_high:
        size = round((TRADE_AMOUNT * leverage) / market_price, 3)
        order = place_order(symbol, 1, size, leverage, tp_list, sl_price)
        if order.get("code") == "0":
            await message.channel.send(f"✅ Trade Placed: {symbol} | Entry: {market_price:.5f}")
        else:
            await message.channel.send(f"❌ Trade Failed: {order}")
    else:
        await message.channel.send(f"⏳ {symbol} not in BUYZONE ({buy_low} - {buy_high}), price was {market_price}")

# Run bot
client.run(DISCORD_TOKEN)
