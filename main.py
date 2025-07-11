import discord
import os
import ccxt
import asyncio
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_RELAY_CHANNEL_ID = int(os.getenv("DISCORD_RELAY_CHANNEL_ID"))
DISCORD_SOURCE_CHANNEL_ID = int(os.getenv("DISCORD_SOURCE_CHANNEL_ID"))

API_KEY = os.getenv("MEXC_API_KEY")
SECRET_KEY = os.getenv("MEXC_SECRET_KEY")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

exchange = ccxt.mexc({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True
})

def parse_signal(msg):
    lines = msg.split("\n")
    symbol = ""
    targets = []
    for line in lines:
        if "USDT" in line:
            symbol = line.strip().replace("/", "").upper()
        elif any(keyword in line for keyword in ["TP", "Target"]):
            num = ''.join(filter(lambda x: x.isdigit() or x == ".", line))
            if num:
                targets.append(float(num))
    return symbol, targets

async def place_order(symbol, targets):
    if not targets or len(targets) < 1:
        print("Invalid TP targets")
        return
    amount = 200  # USDT
    leverage = 100  # leverage
    print(f"Placing trade on {symbol} with TP targets {targets}")
    try:
        markets = exchange.load_markets()
        market = exchange.market(symbol)
        price = exchange.fetch_ticker(symbol)['last']
        qty = round((amount * leverage) / price, 3)
        exchange.set_leverage(leverage, symbol)
        order = exchange.create_market_buy_order(symbol, qty)
        print("Trade placed:", order)
    except Exception as e:
        print("Order failed:", e)

@client.event
async def on_ready():
    print(f"Bot is online as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != DISCORD_SOURCE_CHANNEL_ID:
        return
    if message.author == client.user:
        return
    symbol, targets = parse_signal(message.content)
    if symbol:
        relay_channel = client.get_channel(DISCORD_RELAY_CHANNEL_ID)
        await relay_channel.send(f"📈 Signal Detected: {symbol}\nPlacing Trade Now.")
        await place_order(symbol, targets)

client.run(DISCORD_BOT_TOKEN)
