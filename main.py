import os
import re
import discord
from discord.ext import commands
from dotenv import load_dotenv
import ccxt

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))
MEXC_API_KEY = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(f"[READY] Bot is online as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != RELAY_CHANNEL_ID or message.author.bot:
        return

    content = message.content.strip().upper()
    print(f"[MESSAGE] {content}")

    match = re.search(r"([A-Z]+USDT)", content)
    if not match:
        print("[INFO] No trading pair found.")
        return

    symbol_text = match.group(1)
    base = symbol_text.replace("USDT", "")
    try:
        buyzone = re.search(r"BUYZONE\s*([\d.]+)\s*-\s*([\d.]+)", content).groups()
        buy_price = (float(buyzone[0]) + float(buyzone[1])) / 2
        stop = float(re.search(r"STOP\s*([\d.]+)", content).group(1))
        targets = [float(t) for t in re.findall(r"TARGETS?\s+(.*?)\s+STOP", content, re.S)[0].split()]
        leverage_match = re.search(r"LEVERAGE\s*X?(\d+)", content)
        leverage = int(leverage_match.group(1)) if leverage_match else 5
    except Exception as e:
        print(f"[ERROR] Failed to parse signal: {e}")
        return

    print(f"🚀 Placing market order: BUY {base}/USDT:USDT @ {buy_price} with x{leverage}")

    try:
        exchange = ccxt.mexc({
            'apiKey': MEXC_API_KEY,
            'secret': MEXC_SECRET_KEY,
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'}
        })

        markets = exchange.load_markets()
        symbol = f"{base}/USDT:USDT"

        if symbol not in markets:
            raise Exception(f"Market {symbol} not found on MEXC.")

        market = markets[symbol]
        price = buy_price
        usdt_amount = 200  # Fixed notional
        qty = usdt_amount / price
        qty_rounded = exchange.amount_to_precision(symbol, qty)

        try:
            exchange.set_leverage(leverage, symbol, {
                'openType': 1,
                'positionType': 1
            })
            print(f"[INFO] Leverage set to x{leverage}")
        except Exception as e:
            print(f"[WARNING] Failed to set leverage: {e}")

        order = exchange.create_market_order(
            symbol=symbol,
            side="buy",
            amount=float(qty_rounded),
            params={
                'openType': 1,
                'positionType': 1
            }
        )

        print(f"[SUCCESS] Trade executed: BUY {qty_rounded} {symbol} with x{leverage} leverage")
        print(f"[ORDER INFO] Order ID: {order.get('id')}, Status: {order.get('status')}")

    except Exception as e:
        error_message = f"[ERROR] Trade failed: {str(e)}"
        print(error_message)
        channel = client.get_channel(RELAY_CHANNEL_ID)
        if channel:
            await channel.send(error_message)

client.run(DISCORD_BOT_TOKEN)

# Version check
print("[INFO] ccxt version:", ccxt.__version__)
