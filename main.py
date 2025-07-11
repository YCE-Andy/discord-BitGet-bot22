import os
import re
import discord
from dotenv import load_dotenv
from mexc_sdk import Futures

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))

MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

futures_client = Futures(api_key=MEXC_API_KEY, api_secret=MEXC_SECRET_KEY)

@client.event
async def on_ready():
    print(f"Logged in as {client.user.name}")

@client.event
async def on_message(message):
    if message.channel.id != SOURCE_CHANNEL_ID or message.author.bot:
        return

    try:
        content = message.content
        # Example signal format:
        # KAITOUSDT
        # Entry: 1.50
        # Stop Loss: 1.43
        # Targets: 1.54, 1.58, 1.62, 1.64

        symbol_match = re.search(r"([A-Z]+USDT)", content)
        entry_match = re.search(r"Entry[:\- ]*\$?([\d\.]+)", content, re.IGNORECASE)
        stop_match = re.search(r"Stop\s*Loss[:\- ]*\$?([\d\.]+)", content, re.IGNORECASE)
        targets_match = re.findall(r"1\.\d{2}", content)

        if not (symbol_match and entry_match and stop_match and len(targets_match) >= 1):
            print("Message does not match expected trade format")
            return

        symbol = symbol_match.group(1)
        entry_price = float(entry_match.group(1))
        stop_loss = float(stop_match.group(1))
        targets = [float(t) for t in targets_match[:4]]  # Only use first 4 targets

        usdt_amount = 200
        leverage = 1  # We'll use full leverage allowed in next step

        # Get current price for qty calculation
        ticker = futures_client.get_ticker_price(symbol=symbol)
        current_price = float(ticker["price"])
        quantity = round(usdt_amount / current_price, 3)

        # Set leverage
        futures_client.change_leverage(symbol=symbol, leverage=leverage)

        # Place market order
        order = futures_client.place_order(
            symbol=symbol,
            price=None,
            vol=quantity,
            side=1,  # 1 = open long
            type=1,  # 1 = market
            open_type="isolated",
            position_id=0,
            leverage=leverage,
            external_oid="discord_trade_" + str(message.id),
            stop_loss_price=stop_loss,
            take_profit_price=targets[0]
        )

        print(f"Trade executed: {order}")
    except Exception as e:
        print(f"Error: {e}")

client.run(DISCORD_BOT_TOKEN)
