import os
import time
import hmac
import json
import hashlib
import requests
import discord

# Environment Variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "200"))
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
API_BASE = "https://contract.mexc.com"

client = discord.Client(intents=discord.Intents.all())

# MEXC signing
def sign_request(params, secret):
    query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()

# Market info
def get_symbol_precision(symbol):
    url = f"{API_BASE}/api/v1/contract/detail"
    r = requests.get(url)
    for item in r.json().get("data", []):
        if item["symbol"] == symbol:
            return item["priceScale"], item["volScale"]
    return 2, 3  # Fallback

# Order submit
def place_futures_order(symbol, side, quantity, leverage):
    url = f"{API_BASE}/api/v1/private/order/submit"
    timestamp = int(time.time() * 1000)
    params = {
        "api_key": MEXC_API_KEY,
        "req_time": timestamp,
        "market": symbol,
        "price": 0,
        "vol": quantity,
        "side": 1 if side.lower() == "buy" else 2,
        "type": 1,  # Market
        "open_type": 1,  # Cross margin
        "position_id": 0,
        "leverage": leverage,
        "external_oid": str(timestamp)
    }
    params["sign"] = sign_request(params, MEXC_SECRET_KEY)
    headers = {"Content-Type": "application/json"}
    r = requests.post(url, headers=headers, data=json.dumps(params))
    return r.json()

# Parse Discord signal
def parse_signal(msg):
    parts = msg.upper().split()
    symbol_raw = parts[0].replace("PERP", "").replace("USDT", "")
    symbol = f"{symbol_raw}_USDT"
    leverage = DEFAULT_LEVERAGE
    if "LEVERAGE" in parts:
        idx = parts.index("LEVERAGE")
        try:
            leverage = int(parts[idx + 1].replace("X", ""))
        except: pass
    buyzone_idx = parts.index("BUYZONE")
    entry_low = float(parts[buyzone_idx + 1])
    entry_high = float(parts[buyzone_idx + 3] if parts[buyzone_idx + 2] == "-" else parts[buyzone_idx + 2])
    entry_price = (entry_low + entry_high) / 2
    return symbol, entry_price, leverage

# Events
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id != int(SOURCE_CHANNEL_ID):
        return
    content = message.content.upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        try:
            symbol, price, leverage = parse_signal(content)
            price_prec, vol_prec = get_symbol_precision(symbol)
            qty = round(TRADE_AMOUNT / price, vol_prec)
            alert_channel = client.get_channel(int(ALERT_CHANNEL_ID))
            if alert_channel:
                await alert_channel.send(f"🚀 Placing market order: BUY {symbol} ~{qty} @ {price} with x{leverage}")
            result = place_futures_order(symbol, "buy", qty, leverage)
            if result.get("success"):
                await alert_channel.send(f"✅ Trade Executed: {symbol} x{leverage}")
            else:
                await alert_channel.send(f"❌ Trade Failed: {result}")
        except Exception as e:
            alert_channel = client.get_channel(int(ALERT_CHANNEL_ID))
            if alert_channel:
                await alert_channel.send(f"⚠️ Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
