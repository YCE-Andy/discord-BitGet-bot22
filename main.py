import os
import discord
import re
import asyncio
import ccxt
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))
TRADE_AMOUNT = 200  # USDT

# Setup intents and bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Configure MEXC Futures via CCXT
exchange = ccxt.mexc({
    'apiKey': MEXC_API_KEY,
    'secret': MEXC_SECRET_KEY,
    'options': {'defaultType': 'future'},
    'enableRateLimit': True
})

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Detect symbol and targets in the message
    content = message.content.upper()
    match = re.search(r"(\b[A-Z]+USDT\b).*?TARGETS.*?(\d+\.\d+).*?(\d+\.\d+).*?(\d+\.\d+).*?(\d+\.\d+).*?STOP.*?(\d+\.\d+).*?LEVERAGE.*?(X?\d+)", content, re.DOTALL)

    if match:
        symbol = match.group(1)
        targets = [float(match.group(i)) for i in range(2, 6)]
        stop_loss = float(match.group(6))
        leverage = int(match.group(7).replace("X", ""))

        print(f"📈 Trade detected: {symbol}, TP={targets}, SL={stop_loss}, Leverage={leverage}x")

        try:
            market = exchange.market(symbol)
            exchange.set_leverage(leverage, symbol)

            # Place long market order
            price = exchange.fetch_ticker(symbol)["last"]
            amount = round(TRADE_AMOUNT / price, 3)

            order = exchange.create_market_buy_order(symbol, amount)
            print(f"✅ Market Buy Order Placed: {order['id']}")

            # Optional: notify in channel
            relay_channel = bot.get_channel(RELAY_CHANNEL_ID)
            if relay_channel:
                await relay_channel.send(
                    f"🚀 Trade Executed for {symbol}\nSize: {TRADE_AMOUNT} USDT\nLeverage: {leverage}x\nEntry: {price}\nTP1: {targets[0]} | TP2: {targets[1]} | TP3: {targets[2]} | TP4: {targets[3]} | SL: {stop_loss}"
                )

        except Exception as e:
            print(f"❌ Trade failed: {str(e)}")

    await bot.process_commands(message)

# Run the bot
bot.run(DISCORD_BOT_TOKEN)
