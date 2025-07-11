import discord
import re
import os
import ccxt
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SOURCE_CHANNEL_ID = int(os.getenv('SOURCE_CHANNEL_ID'))
PAIR_WHITELIST = os.getenv('PAIR_WHITELIST', '')  # e.g. "BTCUSDT,ETHUSDT"

mexc = ccxt.mexc({
    'apiKey': os.getenv('MEXC_API_KEY'),
    'secret': os.getenv('MEXC_API_SECRET'),
    'enableRateLimit': True,
})

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def parse_signal(message):
    lines = message.content.split('\n')
    symbol = ''
    direction = ''
    entry = 0.0
    stop_loss = 0.0
    take_profits = []

    for line in lines:
        if 'usdt' in line.lower():
            symbol_match = re.search(r'([A-Z]+USDT)', line.upper())
            if symbol_match:
                symbol = symbol_match.group(1).upper()
        elif any(word in line.lower() for word in ['buy', 'long']):
            direction = 'buy'
        elif any(word in line.lower() for word in ['sell', 'short']):
            direction = 'sell'
        elif 'sl' in line.lower():
            try:
                stop_loss = float(re.findall(r"[\d.]+", line)[0])
            except:
                pass
        elif 'tp' in line.lower():
            try:
                take_profits.append(float(re.findall(r"[\d.]+", line)[0]))
            except:
                pass

    return symbol, direction, stop_loss, take_profits

def place_trade(symbol, direction, stop_loss, tps):
    print(f"Placing trade: {symbol}, direction: {direction}, SL: {stop_loss}, TPs: {tps}")
    market = mexc.fapiPublic_get_premium_index({'symbol': symbol})
    price = float(market['markPrice'])
    amount = 200 / price  # $200 trade size

    side = 'buy' if direction == 'buy' else 'sell'
    order = mexc.create_market_order(symbol=symbol, side=side, amount=amount, params={
        'positionSide': 'LONG' if direction == 'buy' else 'SHORT',
        'leverage': 100
    })
    print("Trade executed:", order)

@client.event
async def on_ready():
    print(f'{client.user} is live and monitoring...')

@client.event
async def on_message(message):
    if message.channel.id != SOURCE_CHANNEL_ID or message.author.bot:
        return

    symbol, direction, sl, tps = parse_signal(message)

    if not symbol or not direction or not sl or len(tps) < 4:
        print("Signal incomplete or invalid.")
        return

    if PAIR_WHITELIST and symbol not in PAIR_WHITELIST.split(','):
        print(f"Symbol {symbol} not whitelisted.")
        return

    try:
        place_trade(symbol, direction, sl, tps[:4])
    except Exception as e:
        print(f"Error placing trade: {e}")

client.run(DISCORD_TOKEN)
