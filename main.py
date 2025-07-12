import os
import discord
import ccxt
import asyncio
import re
import math
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))

exchange = ccxt.mexc({
    'apiKey': os.getenv("MEXC_API_KEY"),
    'secret': os.getenv("MEXC_SECRET_KEY"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',
    }
})

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def parse_message(content):
    try:
        content = content.upper()
        symbol_match = re.search(r'^([A-Z]+USDT)', content)
        base = symbol_match.group(1).replace("USDT", "") if symbol_match else None
        if not base:
            return None

        side = 'buy' if 'BUY' in content else 'sell'
        stop_match = re.search(r'STOP\s*([\d.]+)', content)
        stop = float(stop_match.group(1)) if stop_match else None
        targets = re.findall(r'(?:TARGETS?|^|\n)[\s:]*([\d.]+)', content)
        targets = [float(t) for t in targets if t] if targets else []

        leverage_match = re.search(r'LEVERAGE\s*[Xx]?(\d+)', content)
        leverage = int(leverage_match.group(1)) if leverage_match else 5

        return {
            'base': base,
            'side': side,
            'stop': stop,
            'targets': targets[:4],
            'leverage': leverage
        }
    except Exception as e:
        print(f"[ERROR] Message parsing failed: {e}")
        return None

@client.event
async def on_ready():
    print(f"[READY] Bot is online as {client.user}")
    print("[INFO] Bot loop started")

@client.event
async def on_message(message):
    if message.author == client.user or message.channel.id != RELAY_CHANNEL_ID:
        return

    print(f"[MESSAGE] {message.content} \n\nFrom: {message.author} | Channel: {message.channel.id}")

    trade = parse_message(message.content)
    if not trade:
        print("[ERROR] Message could not be parsed.")
        return

    try:
        exchange.load_markets()
        base = trade["base"]
        side = trade["side"]
        leverage = trade["leverage"]
        notional = 200

        # ✅ Try to match symbol using actual MEXC markets
        valid_symbol = None
        for s in exchange.markets:
            if s.replace("/", "").replace(":", "").upper() == f"{base}USDT":
                valid_symbol = s
                break

        if not valid_symbol:
            raise Exception(f"Market {base}USDT not found on MEXC")

        market_info = exchange.market(valid_symbol)
        price = exchange.fetch_ticker(valid_symbol).get("last")
        if not price or price <= 0:
            raise Exception(f"Invalid price for {valid_symbol}")

        precision_digits = abs(int(round(math.log10(market_info.get("precision", {}).get("amount", 0.0001)))))
        min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.0001)
        qty = max(notional / price, min_qty)
        qty_rounded = round(qty, precision_digits)

        print(f"🚀 Placing market order: {side.upper()} {qty_rounded} {valid_symbol} @ {price} with x{leverage}")

        # ✅ Set leverage
        exchange.set_leverage(
            leverage,
            valid_symbol,
            params={
                'openType': 1,
                'positionType': 1 if side == 'buy' else 2
            }
        )

        # ✅ Create market order
        order = exchange.create_market_order(
            symbol=valid_symbol,
            side=side,
            amount=qty_rounded,
            params={
                'positionSide': 'LONG' if side == 'buy' else 'SHORT'
            }
        )

        print(f"✅ Trade executed: {side.upper()} {qty_rounded} {valid_symbol} with x{leverage} leverage")

    except Exception as e:
        print(f"[ERROR] Trade failed: {e}")
        if hasattr(e, 'args') and isinstance(e.args[0], dict):
            print("📦 API Response:", e.args[0])

client.run(DISCORD_BOT_TOKEN)
