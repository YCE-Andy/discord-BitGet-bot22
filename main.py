import os
import discord
import ccxt
import asyncio
import re
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
exchange.load_markets()  # ✅ This line loads the MEXC market data

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def parse_message(content):
    try:
        content = content.upper()

        symbol_match = re.search(r'^([A-Z]+USDT)', content)
        symbol = symbol_match.group(1) if symbol_match else None

        side = 'buy' if 'BUY' in content else 'sell' if 'SELL' in content else 'buy'

        leverage_match = re.search(r'LEVERAGE\s*X?(\d+)', content)
        leverage = int(leverage_match.group(1)) if leverage_match else 5

        buyzone_match = re.search(r'BUYZONE\s*([\d.]+)\s*-\s*([\d.]+)', content)
        entry = float(buyzone_match.group(1)) if buyzone_match else None

        stop_match = re.search(r'STOP\s*([\d.]+)', content)
        stop_loss = float(stop_match.group(1)) if stop_match else None

        targets_match = re.findall(r'(?:TARGETS?|^|\n)[\s:]*([\d.]+)', content)
        targets = [float(t) for t in targets_match] if targets_match else []

        if not symbol:
            return None

        return {
            'symbol': symbol,
            'side': side,
            'entry': entry,
            'stop_loss': stop_loss,
            'leverage': leverage,
            'targets': targets
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
        leverage = trade["leverage"]

        # Get market details to calculate contract size
        market_info = exchange.market(market)
        price = exchange.fetch_ticker(market)["last"]
        notional = 200  # Use 200 USDT per trade
        quantity = max(
    round(notional / price, int(market_info["precision"]["amount"])),
    market_info["limits"]["amount"]["min"]
)

        order = exchange.create_market_order(
            symbol=market,
            side=side,
            amount=quantity,
            params={
                'positionSide': 'LONG' if side == 'buy' else 'SHORT',
                'leverage': leverage
            }
        )

        print(f"✅ Trade executed: {side.upper()} {quantity} {market} @ market with x{leverage} leverage")
    except Exception as e:
        print(f"❌ Error processing trade: {e}")

client.run(DISCORD_BOT_TOKEN)
