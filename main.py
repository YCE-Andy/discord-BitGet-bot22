import os
import discord
import re
import requests
import json
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ENV VARS
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 200))

HEADERS = {
    "Content-Type": "application/json",
    "ACCESS-KEY": BITGET_API_KEY,
    "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
    "ACCESS-TIMESTAMP": "",
    "ACCESS-SIGN": ""
}

BITGET_BASE_URL = "https://api.bitget.com"

# Simulated signature - replace this with real HMAC signature logic in production.
def sign_request():
    # TODO: Implement proper HMAC SHA256 signature auth
    pass

def place_order(symbol, side, size):
    url = f"{BITGET_BASE_URL}/api/v2/mix/order/place"
    data = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": size,
        "side": side,
        "orderType": "market",
        "price": "",
        "timeInForceValue": "normal",
        "marginMode": "isolated",
        "presetTakeProfitPrice": "",
        "presetStopLossPrice": ""
    }
    response = requests.post(url, headers=HEADERS, json=data)
    return response.json()

def place_tp_sl(symbol, side, price, size, plan_type):
    url = f"{BITGET_BASE_URL}/api/v2/mix/plan/placePlan"
    data = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": size,
        "side": side,
        "triggerPrice": str(price),
        "planType": plan_type,  # profit_plan or loss_plan
        "triggerType": "market_price",
        "executePrice": "",
        "marginMode": "isolated",
        "orderType": "market"
    }
    response = requests.post(url, headers=HEADERS, json=data)
    return response.json()

def extract_signal(message):
    lines = message.content.splitlines()
    symbol = ""
    buyzone = (0, 0)
    targets = []
    stop = 0.0
    leverage = 5
    side = "buy"

    for line in lines:
        if "BUYZONE" in line:
            nums = [float(n) for n in re.findall(r"\d+\.?\d*", line)]
            buyzone = (nums[0], nums[1])
        elif line.startswith("TARGETS"):
            continue
        elif re.match(r"\d+\.\d+", line.strip()):
            targets.append(float(line.strip()))
        elif "STOP" in line:
            stop = float(re.findall(r"\d+\.?\d*", line)[0])
        elif "Leverage" in line:
            leverage = int(re.findall(r"\d+", line)[0])
        elif "SHORT" in line.upper():
            side = "sell"
        elif "USDT" in line.upper():
            symbol = line.strip().replace("(", "").replace(")", "")

    return {
        "symbol": symbol,
        "buyzone": buyzone,
        "targets": targets,
        "stop": stop,
        "leverage": leverage,
        "side": side
    }

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.channel.id != DISCORD_CHANNEL_ID or message.author.bot:
        return

    if "BUYZONE" not in message.content or "TARGETS" not in message.content:
        return

    signal = extract_signal(message)
    symbol = signal["symbol"]
    qty = round(TRADE_AMOUNT / signal["buyzone"][1], 4)

    await message.channel.send(f"🟨 Signal received\n✅ Bitget Order Placed: {symbol} x{signal['leverage']} [{signal['side'].upper()}]")
    order_result = place_order(symbol, signal["side"], qty)
    print(order_result)

    percentages = [0.5, 0.2, 0.15, 0.1, 0.05]
    for i, target in enumerate(signal["targets"][:5]):
        portion = round(qty * percentages[i], 4)
        res = place_tp_sl(symbol, signal["side"], target, portion, "profit_plan")
        await message.channel.send(f"📈 TP @{target}: {res}")

    sl_result = place_tp_sl(symbol, signal["side"], signal["stop"], qty, "loss_plan")
    await message.channel.send(f"🛑 SL @{signal['stop']}: {sl_result}")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
