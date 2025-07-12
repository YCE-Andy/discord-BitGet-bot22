import os
import discord
import ccxt.async_support as ccxt
import asyncio
import re
import math
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RELAY_CHANNEL_ID = int(os.getenv("RELAY_CHANNEL_ID"))

exchange = ccxt.mexc({
    'apiKey': os.getenv("MEXC_API_KEY"),
    'secret': os.getenv("MEXC_SECRET_KEY"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap'  # USDT-M futures
    }
})

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def parse_message(content):
    try:
        content = content.upper()
        symbol_match = re.search(r'^([A-Z]+USDT)', content)
        base = symbol_match.group(1).replace("USDT", "") if symbol_match else None
        if not base:
            return None

        symbol = f"{base}/USDT:USDT"
        side = 'buy' if 'BUY' in content else 'sell'

        stop_match = re.search(r'STOP\s*([\d.]+)', content)
        stop = float(stop_match.group(1)) if stop_match else None

        targets_raw = re.findall(r'(?:TARGETS?|^|\n)[\s:]*([\d.]+)', content)
        targets = []
        for t in targets_raw:
            try:
                val = float(t)
                if val > 0:
                    targets.append(val)
            except ValueError:
                continue

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

@client.event
async def on_ready():
    print(f"[READY] Bot is online as {client.user}")
    print("[INFO] Bot loop started")

@client.event
async def on_message(message):
    if message.author == client.user or message.channel.id != RELAY_CHANNEL_ID:
        return

    print(f"[MESSAGE] {message.content.strip()}\nFrom: {message.author} | Channel: {message.channel.id}")

    trade = parse_message(message.content)
    if not trade:
        print("[ERROR] Invalid trade signal format or parsing failed.")
        return

    try:
        symbol = trade["symbol"]
        side = trade["side"]
        leverage = trade["leverage"]
        notional = 200  # Fixed $200 per trade

        await exchange.load_markets()
        if symbol not in exchange.markets:
            raise Exception(f"Market {symbol} not found on MEXC")

        market = exchange.market(symbol)
        ticker = await exchange.fetch_ticker(symbol)
        price = ticker.get("last")
        if not price or price <= 0:
            raise Exception(f"Invalid price: {price}")

        min_qty = market.get("limits", {}).get("amount", {}).get("min", 0.0001)
        qty = max(notional / price, min_qty)
        qty_rounded = exchange.amount_to_precision(symbol, qty)

        print(f"\U0001F680 Placing market order: {side.upper()} {qty_rounded} {symbol} @ {price} with x{leverage}")

        try:
            await exchange.set_leverage(leverage, symbol, {
                'openType': 1,  # Isolated
                'positionType': 1 if side == 'buy' else 2
            })
            print(f"[INFO] Leverage set to x{leverage}")
        except Exception as e:
            print(f"[WARNING] Failed to set leverage: {e}")

        order = await exchange.create_market_order(
            symbol=symbol,
            side=side,
            amount=float(qty_rounded),
            params={
                'openType': 1,
                'positionType': 1 if side == 'buy' else 2,
                'leverage': leverage
            }
        )

        print(f"[SUCCESS] Trade executed: {side.upper()} {qty_rounded} {symbol} with x{leverage} leverage")
        print(f"[ORDER INFO] Order ID: {order.get('id')}, Status: {order.get('status')}")

    except Exception as e:
        error_message = f"[ERROR] Trade failed: {str(e)}"
        print(error_message)
        channel = client.get_channel(RELAY_CHANNEL_ID)
        if channel:
            await channel.send(error_message)

client.run(DISCORD_BOT_TOKEN)
