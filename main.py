import discord
import re
import time
import hmac
import hashlib
import requests
import json
import os
from discord.ext import commands

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")

API_BASE = "https://contract.mexc.com"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

TRADE_SIGNAL_REGEX = re.compile(
    r"(?P<symbol>[A-Z]+USDT)\s+"
    r"BUYZONE\s+(?P<buyzone_low>[\d.]+)\s*-\s*(?P<buyzone_high>[\d.]+)\s+"
    r"TARGETS\s+(?P<targets>(?:[\d.]+\s*){1,5})\s+"
    r"STOP\s+(?P<stop>[\d.]+)\s+"
    r"LEVERAGE\s*[xX]?(?P<leverage>\d+)"
)

HEADERS = {
    "Content-Type": "application/json",
    "ApiKey": MEXC_API_KEY
}


def sign(params):
    query_string = "&".join([f"{key}={params[key]}" for key in sorted(params)])
    return hmac.new(MEXC_SECRET_KEY.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()


def get_symbol_info():
    url = f"{API_BASE}/api/v1/contract/init"  # This returns futures symbols
    response = requests.get(url)
    return response.json()


def place_order(symbol, price, vol, leverage, side):
    path = "/api/v1/private/order/submit"
    url = API_BASE + path

    order_type = 1  # Market order
    open_type = 1   # Isolated
    position_id = 0
    external_oid = str(int(time.time() * 1000))

    params = {
        "symbol": symbol,
        "price": 0,
        "vol": vol,
        "leverage": leverage,
        "side": 1 if side == "buy" else 2,
        "type": order_type,
        "open_type": open_type,
        "position_id": position_id,
        "external_oid": external_oid,
        "timestamp": int(time.time() * 1000),
    }
    params["sign"] = sign(params)
    response = requests.post(url, headers=HEADERS, data=json.dumps(params))
    return response.json()


@client.event
async def on_ready():
    print(f"[READY] Logged in as {client.user}")


@client.event
async def on_message(message):
    if message.channel.id != RELAY_CHANNEL_ID or message.author == client.user:
        return

    content = message.content.strip()
    match = TRADE_SIGNAL_REGEX.search(content)
    if not match:
        return

    try:
        data = match.groupdict()
        symbol_raw = data['symbol'].upper()
        base_symbol = symbol_raw.replace("USDT", "")

        # Fetch available symbols
        all_symbols = get_symbol_info()
        contracts = all_symbols.get("data", {}).get("symbol", [])

        matched_contract = next((c for c in contracts if c["symbol"] == base_symbol + "_USDT"), None)
        if not matched_contract:
            await message.channel.send(f"[ERROR] Market {symbol_raw} not found on MEXC.")
            return

        mexc_symbol = matched_contract["symbol"]
        entry_price = float(data['buyzone_low'])
        leverage = int(data['leverage'])
        qty = round(20 / entry_price, 2)  # Fixed $20 notional size

        response = place_order(mexc_symbol, entry_price, qty, leverage, "buy")

        if response.get("success"):
            await message.channel.send(f"✅ Trade executed: {symbol_raw} BUY {qty} @ {entry_price} x{leverage}")
        else:
            await message.channel.send(f"❌ Trade failed: {response.get('message') or response}")

    except Exception as e:
        await message.channel.send(f"❌ Trade error: {str(e)}")


client.run(DISCORD_BOT_TOKEN)
