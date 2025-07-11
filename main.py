import os
import discord
import ccxt
import asyncio
import re
import math
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))

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
    content = content.upper()

    symbol_match = re.search(r'^([A-Z]+USDT)', content)
    symbol = symbol_match.group(1) if symbol_match else None
    if symbol:
        symbol = f"{symbol[:-4]}/USDT"

    side = 'buy' if 'BUY' in content else 'sell' if 'SELL' in content else 'buy'

    stop_match = re.search(r'STOP\s*([\d.]+)', content)
    stop_loss = float(stop_match.group(1)) if stop_match else None

    targets_match = re.findall(r'(?:TARGETS?|^|\n)[\s:]*([\d.]+)', content)
    targets = [float(t) for t in targets_match] if targets_match else []

    leverage_match = re.search(r'LEVERAGE\s*x?(\d+)', content)
    leverage = int(leverage_match.group(1)) if leverage_match else 100

    if not symbol:
        return None

    return {
        'symbol': symbol,
        'side': side,
        'stop_loss': stop_loss,
        'targets': targets,
        'leverage': leverage
    }

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
        notional = Decimal("200.00")

        exchange.load_markets()
        if market not in exchange.markets:
            raise Exception(f"Market not found: {market}")

        market_info = exchange.market(market)
        price = Decimal(str(exchange.fetch_ticker(market)['last']))
        precision = market_info['precision']['amount']
        min_qty = Decimal(str(market_info['limits']['amount']['min']))

        # Quantity = notional / price, then round down to allowed precision
        raw_qty = notional / price
        precision_digits = abs(int(math.log10(precision))) if isinstance(precision, float) else precision
        quant_str = str(raw_qty.quantize(Decimal(f'1e-{precision_digits}'), rounding=ROUND_DOWN))

        quantity = Decimal(quant_str)
        if quantity < min_qty:
            quantity = min_qty

        if quantity <= 0:
            raise Exception(f"Invalid quantity calculated: {quantity}")

        print(f"🚀 Placing market order: {side.upper()} {quantity} {market.replace('/', '_')} @ {price} with x{leverage}")

        order = exchange.create_order(
            symbol=market,
            type='market',
            side=side,
            amount=float(quantity),
            price=None,
            params={
                'openType': 1,
                'positionType': 1 if side == 'buy' else 2,
                'leverage': leverage,
                'positionSide': 'LONG' if side == 'buy' else 'SHORT'
            }
        )

        print(f"✅ Trade executed: {side.upper()} {quantity} {market} with x{leverage} leverage")

    except Exception as e:
        print(f"❌ Error processing trade: {e}")
