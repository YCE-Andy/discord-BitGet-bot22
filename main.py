import discord
import os
import re
import ccxt
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))

api_key = os.getenv("MEXC_API_KEY")
secret_key = os.getenv("MEXC_SECRET_KEY")

client = discord.Client(intents=discord.Intents.default().all())

exchange = ccxt.mexc({
    'apiKey': api_key,
    'secret': secret_key,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

@client.event
async def on_ready():
    print(f"✅ Bot is online as {client.user}")

@client.event
async def on_message(message):
    print(f"🔍 Message received: {message.content} | Channel: {message.channel.id} | Author: {message.author}")

    if message.channel.id != RELAY_CHANNEL_ID or message.author == client.user:
        return

    content = message.content.upper()
    try:
        pair_match = re.search(r'^([A-Z]+USDT)', content)
        if not pair_match:
            print("❌ Invalid message format: No pair found")
            return

        symbol = pair_match.group(1)

        tp_matches = re.findall(r'\b\d+\.\d+\b', content)
        if len(tp_matches) < 2:
            print("❌ Not enough price points found in message")
            return

        stop_price = float(re.search(r'STOP[\s:]*([0-9.]+)', content).group(1))
        leverage = int(re.search(r'LEV(?:ERAGE)?[\sx:]*([0-9]+)', content).group(1))
        take_profits = [float(tp) for tp in tp_matches[1:5]]  # First is entry, next 4 are TPs

        side = "buy" if "BUY" in content else "sell"
        market = symbol.replace("USDT", "/USDT")

        balance = exchange.fetch_balance({'type': 'future'})
        usdt_balance = balance['total']['USDT']
        order_amount = 200  # fixed $200 order
        quantity = round(order_amount / float(tp_matches[0]), 2)

        order = exchange.create_market_order(
            symbol=market,
            side=side,
            amount=quantity,
            params={
                'positionSide': 'LONG' if side == 'buy' else 'SHORT',
                'leverage': leverage
            }
        )

        print(f"✅ Trade executed: {side.upper()} {quantity} {symbol} @ market with x{leverage} leverage")
    except Exception as e:
        print(f"❌ Error processing trade: {e}")

client.run(DISCORD_BOT_TOKEN)
