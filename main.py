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

# Setup MEXC exchange client
exchange = ccxt.mexc({
    'apiKey': os.getenv("MEXC_API_KEY"),
    'secret': os.getenv("MEXC_SECRET_KEY"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
    }
})

# Setup Discord bot
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Signal parser
def parse_signal(msg):
    try:
        msg = msg.upper()
        symbol_match = re.search(r'([A-Z]+USDT)', msg)
        symbol = symbol_match.group(1) + "_USDT" if symbol_match else None
        targets = re.findall(r'\b\d+\.\d+\b', msg)
        stop_match = re.search(r'STOP\s*([\d.]+)', msg)
        stop = float(stop_match.group(1)) if stop_match else None
        side = "buy" if "BUY" in msg else "sell"
        return {
            "symbol": symbol,
            "side": side,
            "targets": targets,
            "stop": stop
        } if symbol else None
    except Exception as e:
        print(f"❌ Parse error: {e}")
        return None

@client.event
async def on_ready():
    print(f"✅ Bot is online as {client.user}")
    print("🔁 Starting bot loop...")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    print(f"🔍 Message received: {message.content} | Channel: {message.channel.id} | Author: {message.author}")
    trade = parse_signal(message.content)

    if not trade:
        print("❌ Invalid message format: No pair found or parsing error")
        return

    try:
        symbol = trade["symbol"]
        side = trade["side"]
        leverage = 100  # FORCE LEVERAGE x100
        notional = 200  # FIXED TRADE SIZE

        # Validate market
        exchange.load_markets()
        if symbol not in exchange.markets:
            raise Exception(f"Market {symbol} not found on MEXC")

        market_info = exchange.market(symbol)
        ticker = exchange.fetch_ticker(symbol)
        price = ticker.get("last")

        if price is None or price <= 0:
            raise Exception(f"Invalid price for {symbol}: {price}")

        # Precision
        precision_val = market_info.get("precision", {}).get("amount", 0.0001)
        precision_digits = abs(int(math.log10(precision_val))) if isinstance(precision_val, float) else int(precision_val)

        # Min quantity
        min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.0001)

        # Quantity calc
        raw_qty = notional / price
        quantity = round(max(raw_qty, min_qty), precision_digits)

        if quantity <= 0:
            raise Exception(f"Quantity calculation error: {quantity} for {symbol} at price {price}")

        print(f"🚀 Placing market order: {side.upper()} {quantity} {symbol} @ {price} with x{leverage}")

        # Set leverage (required format for MEXC futures)
        exchange.set_leverage(
            leverage,
            symbol,
            params={
                "openType": 1,  # Isolated
                "positionType": 1 if side == "buy" else 2  # 1=Long, 2=Short
            }
        )

        # Execute market order
        order = exchange.create_market_order(
            symbol=symbol,
            side=side,
            amount=quantity,
            params={
                "positionSide": "LONG" if side == "buy" else "SHORT",
                "leverage": leverage
            }
        )

        print(f"✅ Trade executed: {side.upper()} {quantity} {symbol} with x{leverage} leverage")

    except Exception as e:
        print(f"❌ Error processing trade: {e}")

# Run bot
client.run(DISCORD_BOT_TOKEN)
