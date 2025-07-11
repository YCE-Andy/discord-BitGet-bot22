import os
import discord
import asyncio
import re
from discord.ext import commands
from mexc_sdk import Spot  # pip install mexc-sdk

# Load environment variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")

# Constants
TRADE_AMOUNT_USDT = 200
TP_SPLITS = [0.25, 0.40, 0.25, 0.10]  # Percentage splits for 4 take profits
MAX_TP_COUNT = 4  # Only use the first 4 take profit levels

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Setup MEXC client
client = Spot(key=MEXC_API_KEY, secret=MEXC_SECRET_KEY)

@bot.event
async def on_ready():
    print(f"✅ Bot connected as {bot.user}")

@bot.event
async def on_message(message):
    if message.channel.id != SOURCE_CHANNEL_ID or message.author.bot:
        return

    content = message.content.upper()

    match = re.search(r'^([A-Z]+USDT)', content)
    if not match:
        return

    symbol = match.group(1)
    leverage_match = re.search(r'LEVERAGE\s*X?(\d+)', content)
    leverage = int(leverage_match.group(1)) if leverage_match else 1

    buyzone_match = re.search(r'BUYZONE\s*([\d.]+)\s*-\s*([\d.]+)', content)
    buy_price = float(buyzone_match.group(2)) if buyzone_match else None

    stop_match = re.search(r'STOP\s*([\d.]+)', content)
    stop_loss = float(stop_match.group(1)) if stop_match else None

    target_matches = re.findall(r'(?<=^|\n)([\d.]{3,})', content)
    targets = [float(tp) for tp in target_matches if stop_loss is None or float(tp) > stop_loss]
    targets = targets[:MAX_TP_COUNT]

    # Execute trade if everything needed is present
    if buy_price and stop_loss and targets:
        try:
            order = client.order(symbol=symbol, side="BUY", type="MARKET", quoteOrderQty=TRADE_AMOUNT_USDT)
            print(f"✅ Market order placed for {symbol}: {order}")

            # Send Discord confirmation
            target_channel = bot.get_channel(TARGET_CHANNEL_ID)
            if target_channel:
                tp_msg = "\n".join([f"TP{i+1}: {tp} ({int(TP_SPLITS[i]*100)}%)" for i, tp in enumerate(targets)])
                confirmation = (
                    f"✅ Trade executed for **{symbol}** on MEXC\n"
                    f"• **Buy Amount**: ${TRADE_AMOUNT_USDT}\n"
                    f"• **Leverage**: x{leverage}\n"
                    f"• **Buy Price**: ~{buy_price}\n"
                    f"• **Stop Loss**: {stop_loss}\n"
                    f"• **Take Profits**:\n{tp_msg}"
                )
                await target_channel.send(confirmation)
        except Exception as e:
            print(f"❌ Trade failed: {e}")
            await bot.get_channel(TARGET_CHANNEL_ID).send(f"❌ Trade failed for {symbol}: {e}")
