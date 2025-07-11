import os
import discord
import ccxt
import asyncio
import re
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
        'defaultType': 'future',
    }
})

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def parse_message(content):
    try:
        content = content.upper()

        symbol_match = re.search(r'^([A-Z]+USDT)', content)
        symbol = symbol_match.group(1) if symbol_match else None
        if symbol:
            symbol = f"{symbol[:-4]}_USDT"

        side = 'buy' if 'BUY' in content else 'sell' if 'SELL' in content else 'buy'

        stop_match = re.search(r'STOP\s*([\d.]+)', content)
        stop_loss = float(stop_match.group(1)) if stop_match else None

        targets_match = re.findall(r'(?:TARGETS?|^|\n)[\s:]*([\d.]+)', content)
        targets = [float(t) for t in targets_match] if targets_match else []

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
        market_info = exchange.market(market)
        ticker = exchange.fetch_ticker(market)
        price = ticker.get("last")

        if price is None or price <= 0:
            raise Exception(f"Invalid price: {price}")

        precision = market_info.get("precision", {}).get("amount", 4)
        min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.0001)

        raw_qty = notional / price
        quantity = round(max(raw_qty, min_qty), int(precision))

        if quantity <= 0:
            raise Exception(f"Invalid quantity: {quantity}")

        print(f"🚀 Placing market order: {side.upper()} {quantity} {market} @ {price} with x{leverage}")

        exchange.set_leverage(
            leverage,
            market,
            params={
                'openType': 1,  # Isolated
                'positionType': 1 if side == 'buy' else 2
            }
        )

        order = exchange.create_market_order(
    symbol=market,
    side=side,
    amount=quantity,
    params={
        'openType': 1,
        'positionType': 1 if side == 'buy' else 2,
        'positionSide': 'LONG' if side == 'buy' else 'SHORT'
    }
)

        print(f"✅ Trade executed: {side.upper()} {quantity} {market} with x{leverage} leverage")

    except Exception as e:
        print(f"❌ Error processing trade: {e}")

client.run(DISCORD_BOT_TOKEN)
