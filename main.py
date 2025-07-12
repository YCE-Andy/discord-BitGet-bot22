import discord
import re
import time
import hmac
import hashlib
import requests
import os

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
API_BASE = "https://contract.mexc.com"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def parse_signal(message):
    pattern = re.compile(
        r"([A-Z]+USDT).*?BUYZONE\s+([\d\.]+)\s*-\s*([\d\.]+).*?TARGETS\s+([\d\s\.]+).*?STOP\s+([\d\.]+).*?(LEVERAGE\s+x?(\d+))?",
        re.DOTALL
    )
    match = pattern.search(message)
    if not match:
        return None

    symbol = match.group(1).replace("PERP", "").replace("1000", "").upper()
    entry_low = float(match.group(2))
    entry_high = float(match.group(3))
    targets = [float(t) for t in match.group(4).split()]
    stop_loss = float(match.group(5))
    leverage = int(match.group(7)) if match.group(7) else 5
    return {
        "symbol": symbol,
        "entry": (entry_low + entry_high) / 2,
        "targets": targets[:4],
        "stop": stop_loss,
        "leverage": leverage
    }

def get_symbol_info():
    url = f"{API_BASE}/api/v1/contract/init"
    response = requests.get(url)
    return response.json().get("data", [])

def find_market(symbol):
    all_symbols = get_symbol_info()
    for market in all_symbols:
        if market["symbol"] == symbol:
            return market["symbol"]
    return None

def place_futures_order(symbol, side, quantity, leverage):
    path = "/api/v1/private/order/submit"
    url = API_BASE + path
    timestamp = int(time.time() * 1000)

    order_params = {
        "api_key": MEXC_API_KEY,
        "req_time": timestamp,
        "market": symbol,
        "price": 0,
        "vol": quantity,
        "leverage": leverage,
        "side": 1 if side == "buy" else 2,
        "type": 1,
        "open_type": 1,
        "position_id": 0,
        "external_oid": str(timestamp),
        "stop_loss_price": 0,
        "take_profit_price": 0,
        "position_mode": 1
    }

    sign_str = '&'.join([f"{k}={order_params[k]}" for k in sorted(order_params)])
    signature = hmac.new(
        MEXC_SECRET_KEY.encode(),
        sign_str.encode(),
        hashlib.sha256
    ).hexdigest()
    order_params["sign"] = signature

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, data=order_params, headers=headers)
    return response.json()

@client.event
async def on_ready():
    print(f"[READY] Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID or message.author.bot:
        return

    signal = parse_signal(message.content)
    if not signal:
        return

    symbol = find_market(signal["symbol"])
    if not symbol:
        await message.channel.send(f"❌ [ERROR] Market {signal['symbol']} not found on MEXC.")
        return

    price = signal["entry"]
    amount = 200 / price  # fixed 200 USDT
    amount = round(amount, 3)

    await message.channel.send(f"🚀 Placing market order: BUY {symbol} ~{amount} @ {price} with x{signal['leverage']}")

    result = place_futures_order(symbol, "buy", amount, signal["leverage"])
    if result.get("success"):
        await message.channel.send(f"✅ Trade executed successfully: {result}")
    else:
        await message.channel.send(f"❌ Trade failed: {result}")

client.run(DISCORD_BOT_TOKEN)
