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
        'defaultType': 'swap',  # ✅ Use futures (USDT-M)
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

        symbol = f"{base}/USDT:USDT"  # ✅ Proper format for MEXC USDT-M futures
        side = 'buy' if 'BUY' in content else 'sell'
        stop_match = re.search(r'STOP\s*([\d.]+)', content)
        stop = float(stop_match.group(1)) if stop_match else None
        targets_match = re.findall(r'(?:TARGETS?|^|\n)[\s:]*([\d.]+)', content)
        targets = [float(t) for t in targets_match] if targets_match else []

        return {
            'symbol': symbol,
            'side': side,
            'stop': stop,
            'targets': targets,
        }
    except Exception as e:
        print(f"❌ Error parsing message: {e}")
        return None

@client.event
async def on_ready():
    print(f"✅ Bot is online as {client.user}")
    print("🔁 Starting bot loop...")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id != RELAY_CHANNEL_ID:
        return

    print(f"🔍 Message received: {message.content} | Channel: {message.channel.id} | Author: {message.author}")

    trade = parse_message(message.content)
    if not trade:
        print("❌ Invalid message format: No pair found or parsing error")
        return

    try:
        market = trade["symbol"]
        side = trade["side"]
        leverage = 100
        notional = 200

        exchange.load_markets()
        if market not in exchange.markets:
            raise Exception(f"Market {market} not found on MEXC")

        market_info = exchange.market(market)
        price = exchange.fetch_ticker(market).get("last")
        if not price or price <= 0:
            raise Exception(f"Invalid price: {price}")

        precision = market_info.get("precision", {}).get("amount", 0.0001)
        if isinstance(precision, float):
            precision_digits = abs(int(round(math.log10(precision))))
        else:
            precision_digits = int(precision)

        min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.0001)
        raw_qty = notional / price
        qty_rounded = round(max(raw_qty, min_qty), precision_digits)

        if qty_rounded <= 0:
            raise Exception(f"Invalid quantity: {qty_rounded}")

        print(f"🚀 Placing market order: {side.upper()} {qty_rounded} {market} @ {price} with x{leverage}")

        # ✅ Set leverage with required openType and positionType
        exchange.set_leverage(
            leverage,
            market,
            params={
                'openType': 1,  # Isolated
                'positionType': 1 if side == 'buy' else 2  # 1 = long, 2 = short
            }
        )

        order = exchange.create_market_order(
            symbol=market,
            side=side,
            amount=qty_rounded,
            params={
                'positionSide': 'LONG' if side == 'buy' else 'SHORT',
                'leverage': leverage
            }
        )

        print(f"✅ Trade executed: {side.upper()} {qty_rounded} {market} with x{leverage} leverage")

    except Exception as e:
        print(f"❌ Error processing trade: {e}")

client.run(DISCORD_BOT_TOKEN)
