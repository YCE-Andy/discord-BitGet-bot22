import os
import discord
import ccxt
import re
import math
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))

# Configure MEXC Futures
exchange = ccxt.mexc({
    'apiKey': os.getenv("MEXC_API_KEY"),
    'secret': os.getenv("MEXC_SECRET_KEY"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',  # IMPORTANT: This is required for futures
    }
})

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def parse_message(content):
    try:
        content = content.upper()
        symbol_match = re.search(r'([A-Z]+USDT)', content)
        symbol = symbol_match.group(1) if symbol_match else None
        side = 'buy' if 'BUY' in content else 'sell' if 'SELL' in content else 'buy'
        stop_match = re.search(r'STOP\s*([\d.]+)', content)
        stop_loss = float(stop_match.group(1)) if stop_match else None
        targets = re.findall(r'(?:TARGETS?|^|\n)[\s:]*([\d.]+)', content)
        targets = [float(t) for t in targets] if targets else []
        return {
            'symbol': symbol,
            'side': side,
            'stop_loss': stop_loss,
            'targets': targets
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

    if message.channel.id != RELAY_CHANNEL_ID:
        return

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
        price = exchange.fetch_ticker(market)["last"]
        if not price or price <= 0:
            raise Exception(f"Invalid price for {market}")

        precision = market_info.get("precision", {}).get("amount", 0.0001)
        precision_digits = abs(int(math.log10(precision))) if isinstance(precision, float) else 4
        min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.0001)

        raw_qty = notional / price
        qty = round(max(raw_qty, min_qty), precision_digits)

        if qty <= 0:
            raise Exception(f"Final quantity invalid: {qty}")

        print(f"🚀 Placing market order: {side.upper()} {qty} {market} @ {price} with x{leverage}")

        order = exchange.create_market_order(
            symbol=market,
            side=side,
            amount=qty,
            params={
                'positionSide': 'LONG' if side == 'buy' else 'SHORT',
                'leverage': leverage,
                'openType': 1,  # 1 = isolated margin
                'positionType': 1 if side == 'buy' else 2  # 1 = long, 2 = short
            }
        )

        print(f"✅ Trade executed: {side.upper()} {qty} {market} with x{leverage} leverage")
    except Exception as e:
        print(f"❌ Error processing trade: {e}")

client.run(DISCORD_BOT_TOKEN)
