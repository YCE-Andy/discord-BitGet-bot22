import os
import discord
import ccxt
import asyncio
import re
import math
from dotenv import load_dotenv

# Load .env secrets
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))

# Initialize MEXC exchange (USDT-M futures)
exchange = ccxt.mexc({
    'apiKey': os.getenv("MEXC_API_KEY"),
    'secret': os.getenv("MEXC_SECRET_KEY"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',  # ✅ For futures trading
    }
})
exchange.load_markets()  # ✅ Ensure futures markets are loaded (e.g., FILUSDT)

# Initialize Discord client
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Parse signal message
def parse_message(content):
    try:
        content = content.upper()
        symbol_match = re.search(r'^([A-Z]+USDT)', content)
        base = symbol_match.group(1).replace("USDT", "") if symbol_match else None
        if not base:
            return None

        symbol = f"{base}USDT"  # ✅ Proper format for MEXC USDT-M Futures
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
        print(f"[ERROR] Parse failed: {e}")
        return None

# Bot ready
@client.event
async def on_ready():
    print(f"[READY] Bot is online as {client.user}")
    print("[INFO] Bot loop started")

# Bot message handler
@client.event
async def on_message(message):
    if message.author == client.user or message.channel.id != RELAY_CHANNEL_ID:
        return

    print(f"[MESSAGE] {message.content}\n\nFrom: {message.author} | Channel: {message.channel.id}")

    trade = parse_message(message.content)
    if not trade:
        print("[ERROR] Invalid signal format.")
        return

    try:
        symbol = trade["symbol"]
        side = trade["side"]
        leverage = trade["leverage"]
        notional = 200  # Fixed USDT amount per trade

        if symbol not in exchange.markets:
            raise Exception(f"Market {symbol} not found on MEXC")

        market = exchange.market(symbol)
        price = exchange.fetch_ticker(symbol).get("last")
        if not price or price <= 0:
            raise Exception(f"Invalid price: {price}")

        precision = market.get("precision", {}).get("amount", 0.0001)
        if isinstance(precision, float):
            precision_digits = abs(int(round(math.log10(precision))))
        else:
            precision_digits = int(precision)

        min_qty = market.get("limits", {}).get("amount", {}).get("min", 0.0001)
        raw_qty = max(notional / price, min_qty)
        qty = round(raw_qty, precision_digits)

        print(f"🚀 Placing market order: {side.upper()} {qty} {symbol} @ {price} with x{leverage}")

        # Set leverage
        exchange.set_leverage(
            leverage,
            symbol,
            params={
                'openType': 1,  # Isolated
                'positionType': 1 if side == 'buy' else 2  # 1 = Long, 2 = Short
            }
        )

        # Place market order
        order = exchange.create_market_order(
            symbol=symbol,
            side=side,
            amount=qty,
            params={
                'openType': 1,
                'positionType': 1 if side == 'buy' else 2
            }
        )

        print(f"✅ Trade executed: {side.upper()} {qty} {symbol} with x{leverage} leverage")

    except Exception as e:
        print(f"[ERROR] Trade failed: {e}")
        if hasattr(e, 'args') and isinstance(e.args[0], dict):
            print("[DETAILS]", e.args[0])

# Start the bot
client.run(DISCORD_BOT_TOKEN)
