import os
import discord
import ccxt
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
        'defaultType': 'swap',  # Futures trading
    }
})

intents = discord.Intents.default()
intents.message_content = True  # Must be True to receive messages
client = discord.Client(intents=intents)

def parse_message(content):
    try:
        content = content.upper()
        symbol_match = re.search(r'^([A-Z]+USDT)', content)
        symbol = symbol_match.group(1) if symbol_match else None
        if symbol:
            symbol = symbol.replace("USDT", "_USDT")  # MEXC format for futures

        side = 'buy' if 'BUY' in content else 'sell' if 'SELL' in content else 'buy'
        leverage_match = re.search(r'LEVERAGE\s*x?(\d+)', content)
        leverage = int(leverage_match.group(1)) if leverage_match else 100

        return {
            'symbol': symbol,
            'side': side,
            'leverage': leverage
        }
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

    if message.channel.id != RELAY_CHANNEL_ID:
        return

    trade = parse_message(message.content)
    if not trade:
        print("❌ Invalid message format.")
        return

    try:
        market = trade['symbol']
        side = trade['side']
        leverage = trade['leverage']
        notional = 200  # Fixed 200 USDT per trade

        exchange.load_markets()
        if market not in exchange.markets:
            raise Exception(f"Market {market} not found on MEXC")

        market_info = exchange.market(market)
        price = exchange.fetch_ticker(market)['last']

        if not price or price <= 0:
            raise Exception(f"Invalid price for {market}: {price}")

        # Precision + Quantity
        precision = market_info['precision']['amount']
        precision_digits = abs(int(math.log10(precision))) if precision else 4
        min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.0001)

        raw_qty = notional / price
        quantity = max(round(raw_qty, precision_digits), min_qty)

        print(f"🚀 Placing market order: {side.upper()} {quantity} {market} @ {price} with x{leverage}")

        # Set leverage
        exchange.set_leverage(
            leverage,
            market,
            params={
                'openType': 1,  # Isolated
                'positionType': 1 if side == 'buy' else 2
            }
        )

        # Place market order
        order = exchange.create_market_order(
            symbol=market,
            side=side,
            amount=quantity,
            params={
                'openType': 1,
                'positionType': 1 if side == 'buy' else 2
            }
        )

        print(f"✅ Trade executed: {side.upper()} {quantity} {market} at {price} with x{leverage} leverage")

    except Exception as e:
        print(f"❌ Error processing trade: {e}")

client.run(DISCORD_BOT_TOKEN)
