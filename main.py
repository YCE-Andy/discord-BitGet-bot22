import os
import discord
import requests
import json
import re
from discord import Intents
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_SOURCE_CHANNEL_ID"))
ALERT_CHANNEL_ID = int(os.getenv("DISCORD_RELAY_CHANNEL_ID"))
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 200))
LEVERAGE = int(os.getenv("LEVERAGE", 5))

def get_headers():
    return {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": "",
        "ACCESS-TIMESTAMP": str(datetime.utcnow().timestamp()),
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def place_order(symbol, side, size, leverage):
    url = "https://api.bitget.com/api/v2/mix/order/place-order"
    data = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": side,
        "orderType": "market",
        "size": size,
        "leverage": leverage,
        "tradeSide": "open"  # assume always opening
    }
    headers = get_headers()
    response = requests.post(url, headers=headers, json=data)
    return response.json()

def place_tp_sl(symbol, marginCoin, tp_levels, sl_price, is_long):
    base_url = "https://api.bitget.com/api/v2/mix/order/place-plan-order"
    headers = get_headers()
    side = "close_long" if is_long else "close_short"
    tp_percents = [0.5, 0.2, 0.15, 0.10, 0.05]  # TP split

    for i, tp in enumerate(tp_levels[:5]):
        tp_data = {
            "symbol": symbol,
            "marginCoin": marginCoin,
            "size": "",  # You must determine actual contract size here based on position size
            "executePrice": tp,
            "triggerPrice": tp,
            "triggerType": "fill_price",
            "orderType": "limit",
            "side": side,
            "planType": "profit_plan"
        }
        requests.post(base_url, headers=headers, json=tp_data)

    sl_data = {
        "symbol": symbol,
        "marginCoin": marginCoin,
        "size": "",  # You must determine actual contract size here based on position size
        "triggerPrice": sl_price,
        "triggerType": "fill_price",
        "orderType": "market",
        "side": side,
        "planType": "loss_plan"
    }
    requests.post(base_url, headers=headers, json=sl_data)

intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != CHANNEL_ID or message.author == client.user:
        return

    content = message.content
    pattern = re.compile(r"(?P<symbol>\w+USDT)(?: \(SHORT\))?.*?BUYZONE (?P<buy1>\d+\.\d+) - (?P<buy2>\d+\.\d+).*?TARGETS\n(?P<targets>[\d\.\n ]+).*?STOP (?P<stop>\d+\.\d+).*?Leverage x(?P<lev>\d+)", re.DOTALL)
    match = pattern.search(content)
    if match:
        symbol = match.group("symbol").strip().upper()
        targets = [float(t.strip()) for t in match.group("targets").strip().splitlines() if t.strip()]
        stop = float(match.group("stop"))
        leverage = int(match.group("lev"))
        is_short = "SHORT" in content.upper()
        side = "sell" if is_short else "buy"

        # Calculate size from TRADE_AMOUNT and market price — this is simplified
        # You should retrieve actual market price for precision
        size = str(TRADE_AMOUNT)  # Replace with precision logic if needed

        order_response = place_order(symbol, side, size, leverage)

        if order_response.get("code") == "00000":
            alert_msg = f"✅ Bitget Order Placed: {symbol} x{leverage} [{'SELL' if is_short else 'BUY'}]"
            await message.channel.send(alert_msg)

            # Place TP/SL based on parsed targets and stop
            place_tp_sl(symbol, "USDT", targets, stop, not is_short)
        else:
            await message.channel.send(f"❌ Bitget Order Failed: {order_response}")

client.run(DISCORD_TOKEN)
