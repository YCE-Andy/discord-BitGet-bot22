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
        'defaultType': 'swap',  # Use USDT-M Futures
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

        symbol = f"{base}/USDT:USDT"
        side = 'buy' if 'BUY' in content else 'sell'
        stop_match = re.search(r'STOP\s*([\d.]+)', content)
        stop = float(stop_match.group(1)) if stop_match else None
        targets = re.findall(r'(?:TARGETS?|^|\n)[\s:]*([\d.]+)', content)
        targets = [float(t) for t in targets] if targets else []

        leverage_match = re.search(r'LEVERAGE\s*[Xx]?(\d+)', content)
        leverage = int(leverage_match.group(1)) if leverage_match else 5

        return {
            'symbol': symbol,
            'side': side,
            'stop': stop,
            'targets': targets[:4],
            'leverage': leverage
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
    if message.author == client.user or message.channel.id != RELAY_CHANNEL_ID:
        return

    print(f"🔍 Message received: {message.content} | Channel: {message.channel.id} | Author: {message.author}")

    trade = parse_message(message.content)
    if not trade:
        print("❌ Invalid message format or symbol")
        return

    try:
        symbol = trade["symbol"]
        side = trade["side"]
        leverage = trade["leverage"]
        notional = 200

        exchange.load_markets()
        if symbol not in exchange.markets:
            raise Exception(f"Market {symbol} not found on MEXC")

        market = exchange.market(symbol)
        price = exchange.fetch_ticker(symbol).get("last")
        if not price or price <= 0:
            raise Exception(f"Invalid price: {price}")

        precision_digits = abs(int(round(math.log10(market.get("precision", {}).get("amount", 0.0001)))))
        min_qty = market.get("limits", {}).get("amount", {}).get("min", 0.0001)
        qty = max(notional / price, min_qty)
        qty_rounded = round(qty, precision_digits)

                # ✅ Strip unsupported parameters
        print(f"🚀 Placing market order: {side.upper()} {qty_rounded} {symbol} @ {price} with x{leverage}")

        # ✅ Set leverage
        exchange.set_leverage(leverage, symbol)

        # ✅ Create the market order (no positionSide)
       order = exchange.create_market_order(
    symbol=symbol,
    side=side,
    amount=qty_rounded,
    params={
        'positionSide': 'LONG' if side == 'buy' else 'SHORT',
        'leverage': leverage
    }
)

        order = exchange.create_market_order(
            symbol=symbol,
            side=side,
            amount=qty_rounded,
            params={
                'positionSide': 'LONG' if side == 'buy' else 'SHORT',
                'leverage': leverage
            }
        )

        print(f"✅ Trade executed: {side.upper()} {qty_rounded} {symbol} with x{leverage} leverage")

    except Exception as e:
        print(f"❌ Error processing trade: {e}")
        if hasattr(e, 'args') and isinstance(e.args[0], dict):
            print("📦 MEXC error response:", e.args[0])

client.run(DISCORD_BOT_TOKEN)
