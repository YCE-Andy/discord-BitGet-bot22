import os
import discord
import ccxt
import asyncio
import re
import math
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))

# Configure MEXC exchange
exchange = ccxt.mexc({
    'apiKey': os.getenv("MEXC_API_KEY"),
    'secret': os.getenv("MEXC_SECRET_KEY"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
    }
})

# Set up Discord client with message content intent
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Parse trading signal
def parse_message(content):
    try:
        content = content.upper()

        symbol_match = re.search(r'([A-Z]+USDT)', content)
        symbol = symbol_match.group(1).replace("USDT", "") + "_USDT" if symbol_match else None

        side = "buy" if "BUY" in content else "sell" if "SELL" in content else "buy"

        stop_match = re.search(r'STOP\s*([\d.]+)', content)
        stop_loss = float(stop_match.group(1)) if stop_match else None

        targets = re.findall(r'TARGETS?.*?([\d.]+)', content, re.DOTALL)
        targets = [float(t) for t in targets] if targets else []

        leverage_match = re.search(r'LEVERAGE\s*[xX]?(\d+)', content)
        leverage = int(leverage_match.group(1)) if leverage_match else 100  # Force x100 default

        return {
            'symbol': symbol,
            'side': side,
            'stop_loss': stop_loss,
            'targets': targets[:4],
            'leverage': leverage
        }
    except Exception as e:
        print(f"❌ Error parsing message: {e}")
        return None

# On bot ready
@client.event
async def on_ready():
    print(f"✅ Bot is online as {client.user}")
    print("🔁 Starting bot loop...")

# On new message
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    print(f"🔍 Message received: {message.content} | Channel: {message.channel.id} | Author: {message.author}")

    if message.channel.id != RELAY_CHANNEL_ID:
        return

    trade = parse_message(message.content)
    if not trade:
        print("❌ Invalid message format: No pair found or parsing error")
        return

    try:
        symbol = trade["symbol"]
        side = trade["side"]
        leverage = 100  # Always force x100 leverage
        notional = 200  # Always use 200 USDT

        exchange.load_markets()
        market_info = exchange.market(symbol)
        price = exchange.fetch_ticker(symbol)['last']

        if not price or price <= 0:
            raise Exception(f"Invalid market price: {price}")

        # Determine precision
        precision = market_info.get("precision", {}).get("amount", 0.0001)
        precision_digits = abs(int(round(math.log10(precision)))) if isinstance(precision, float) else int(precision)

        min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.0001)
        raw_qty = notional / price
        qty = max(round(raw_qty, precision_digits), min_qty)

        if qty <= 0:
            raise Exception(f"Calculated quantity is zero or less. Qty: {qty}, Raw: {raw_qty}, Price: {price}")

        print(f"🚀 Placing market order: {side.upper()} {qty} {symbol} @ {price} with x{leverage}")

        # Set leverage with correct params
        exchange.set_leverage(leverage, symbol, params={
            "openType": 1,  # Isolated
            "positionType": 1 if side == "buy" else 2  # Long or Short
        })

        # Place order
        order = exchange.create_market_order(
            symbol=symbol,
            side=side,
            amount=qty,
            params={
                "positionSide": "LONG" if side == "buy" else "SHORT",
                "leverage": leverage,
                "openType": 1,  # Isolated
                "positionType": 1 if side == "buy" else 2
            }
        )

        print(f"✅ Trade executed: {side.upper()} {qty} {symbol} with x{leverage} leverage")

    except Exception as e:
        print(f"❌ Error processing trade: {e}")
