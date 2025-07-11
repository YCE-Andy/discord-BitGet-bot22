import os
import discord
import ccxt
import re
import math
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))

# Configure MEXC futures
exchange = ccxt.mexc({
    'apiKey': os.getenv("MEXC_API_KEY"),
    'secret': os.getenv("MEXC_SECRET_KEY"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
    }
})

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def parse_message(content):
    try:
        content = content.upper()

        # Extract symbol (e.g. MANAUSDT)
        match = re.search(r'^([A-Z]+USDT)', content)
        symbol = match.group(1) if match else None
        if symbol:
            symbol = f"{symbol[:-4]}/USDT"  # Convert to MANA/USDT

        side = 'buy' if 'BUY' in content else 'sell' if 'SELL' in content else 'buy'

        return {
            'symbol': symbol,
            'side': side
        } if symbol else None

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

    print(f"🔍 Message received: {message.content} | Channel: {message.channel.id} | Author: {message.author}")

    trade = parse_message(message.content)
    if not trade:
        print("❌ Invalid message format: No pair found or parsing error")
        return

    try:
        market = trade["symbol"]
        side = trade["side"]
        leverage = 100  # Force x100 leverage
        notional = 200  # Always use 200 USDT

        exchange.load_markets()
        if market not in exchange.markets:
            raise Exception(f"Market {market} not found on MEXC")

        market_info = exchange.market(market)
        ticker = exchange.fetch_ticker(market)
        price = ticker.get("last")

        if price is None or price <= 0:
            raise Exception(f"Invalid price: {price}")

        # Get precision and min quantity
        amount_precision = market_info.get("precision", {}).get("amount", 0.0001)
        precision_digits = abs(int(round(-math.log10(amount_precision)))) if amount_precision < 1 else 2
        min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.0001)

        # Calculate quantity
        raw_qty = notional / price
        quantity = round(max(raw_qty, min_qty), precision_digits)

        if quantity <= 0:
            raise Exception(f"Invalid final quantity: {quantity} for notional {notional} and price {price}")

        print(f"🚀 Placing market order: {side.upper()} {quantity} {market} @ {price} with x{leverage}")

        # Set leverage
        exchange.set_leverage(leverage, market)

        order = exchange.create_market_order(
            symbol=market,
            side=side,
            amount=quantity,
            params={
                'positionSide': 'LONG' if side == 'buy' else 'SHORT'
            }
        )

        print(f"✅ Trade executed: {side.upper()} {quantity} {market} with x{leverage} leverage")

    except Exception as e:
        print(f"❌ Error processing trade: {e}")

client.run(DISCORD_BOT_TOKEN)
