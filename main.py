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

# Configure MEXC exchange with credentials
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

        # Extract symbol like MANAUSDT and convert to MANA/USDT
        symbol_match = re.search(r'^([A-Z]+USDT)', content)
        symbol = symbol_match.group(1) if symbol_match else None
        if symbol:
            symbol = f"{symbol[:-4]}/USDT"  # e.g., MANAUSDT -> MANA/USDT

        side = 'buy' if 'BUY' in content else 'sell' if 'SELL' in content else 'buy'

        # Extract stop loss (optional)
        stop_match = re.search(r'STOP\s*([\d.]+)', content)
        stop_loss = float(stop_match.group(1)) if stop_match else None

        # Extract targets
        targets_match = re.findall(r'(?:TARGETS?|^|\n)[\s:]*([\d.]+)', content)
        targets = [float(t) for t in targets_match] if targets_match else []

        # Extract leverage
        leverage_match = re.search(r'LEVERAGE\s*x?(\d+)', content)
        leverage = int(leverage_match.group(1)) if leverage_match else 100  # force 100 if not found

        if not symbol:
            return None

        return {
            'symbol': symbol,
            'side': side,
            'stop_loss': stop_loss,
            'targets': targets,
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
        leverage = 100  # Forced leverage
        notional = 200  # Fixed USDT per trade

        exchange.load_markets()
        if market not in exchange.markets:
            raise Exception(f"Market not found: {market}")
        market_info = exchange.market(market)
        ticker = exchange.fetch_ticker(market)
        price = ticker.get("last")

        if price is None or price <= 0:
            raise Exception(f"Invalid price: {price}")

        # Fallbacks
        precision = market_info.get("precision", {}).get("amount", 4)
        if isinstance(precision, float):
            precision_digits = abs(int(math.log10(precision)))
        else:
            precision_digits = precision
        min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.0001)

        # Safe quantity calc
        raw_qty = notional / price
        quantity = round(max(raw_qty, min_qty), precision_digits)

        if quantity <= 0:
            raise Exception(f"Invalid final quantity: {quantity} for notional {notional} and price {price}")

        print(f"🚀 Placing market order: {side.upper()} {quantity} {market.replace('/', '_')} @ {price} with x{leverage}")

        # Place order with required MEXC params
        order = exchange.create_order(
            symbol=market,
            type='market',
            side=side,
            amount=quantity,
            price=None,
            params={
                'openType': 1,  # 1 = isolated
                'positionType': 1 if side == 'buy' else 2,  # 1 = long, 2 = short
                'leverage': leverage,
                'positionSide': 'LONG' if side == 'buy' else 'SHORT'
            }
        )

        print(f"✅ Trade executed: {side.upper()} {quantity} {market} with x{leverage} leverage")

    except Exception as e:
        print(f"❌ Error processing trade: {e}")

client.run(DISCORD_BOT_TOKEN)
