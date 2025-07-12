import os
import discord
import ccxt
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
        'defaultType': 'swap',   # ✅ MEXC Futures (USDT-M)
    }
})

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def parse_message(content):
    try:
        content = content.upper()
        # Look for a pattern like XXXUSDT at the beginning of the message
        symbol_match = re.search(r'^([A-Z]+USDT)', content)
        base = symbol_match.group(1).replace("USDT", "") if symbol_match else None
        if not base:
            return None

        # Change this line to format the symbol as BASE/USDT
        symbol = f"{base}/USDT"  # Correct format for MEXC futures with CCXT

        side = 'buy' if 'BUY' in content else 'sell'
        stop_match = re.search(r'STOP\s*([\d.]+)', content)
        stop = float(stop_match.group(1)) if stop_match else None
        # Adjusting target extraction to be more robust
        targets_raw = re.findall(r'(?:TARGETS?|^|\n)[\s:]*([\d.]+)', content)
        targets = []
        for t in targets_raw:
            try:
                val = float(t)
                if val > 0:
                    targets.append(val)
            except ValueError:
                continue # Skip if it's not a valid number
        
        leverage_match = re.search(r'LEVERAGE\s*[Xx]?(\d+)', content)
        leverage = int(leverage_match.group(1)) if leverage_match else 5

        return {
            'symbol': symbol,
            'side': side,
            'stop': stop,
            'targets': targets[:4], # Limit to first 4 targets
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

    print(f"[MESSAGE] {message.content.strip()} \nFrom: {message.author} | Channel: {message.channel.id}")

    trade = parse_message(message.content)
    if not trade:
        print("[ERROR] Invalid trade signal format or parsing failed.")
        return

    try:
        symbol = trade["symbol"]
        side = trade["side"]
        leverage = trade["leverage"]
        notional = 200   # USDT fixed value

        exchange.load_markets()
        if symbol not in exchange.markets:
            raise Exception(f"Market {symbol} not found on MEXC. Available markets for 'swap': {', '.join([s for s, m in exchange.markets.items() if m['type'] == 'swap'])}")

        market = exchange.market(symbol)
        
        # Fetch ticker using async method
        ticker = await exchange.fetch_ticker(symbol)
        price = ticker.get("last")
        if not price or price <= 0:
            raise Exception(f"Invalid price: {price}")

        # Ensure precision is handled correctly for floating point numbers
        # Use .get with a default for safety
        amount_precision = market.get("precision", {}).get("amount", None)
        if amount_precision is not None:
             precision_digits = abs(int(round(math.log10(amount_precision)))) if amount_precision != 0 else 8 # Default if 0
        else:
            precision_digits = 8 # A reasonable default if precision is missing

        min_qty = market.get("limits", {}).get("amount", {}).get("min", 0.0001)
        qty = max(notional / price, min_qty)
        qty_rounded = exchange.amount_to_precision(symbol, qty) # Use CCXT's precision helper

        print(f"🚀 Placing market order: {side.upper()} {qty_rounded} {symbol} @ {price} with x{leverage}")

        # ✅ Set leverage
        # Note: set_leverage can sometimes return an error if leverage is already set or invalid for the market.
        # Consider wrapping in a try-except if this becomes an issue.
        try:
            await exchange.set_leverage(leverage, symbol, {
                'openType': 1,   # Isolated
                'positionType': 1 if side == 'buy' else 2   # 1=long, 2=short
            })
            print(f"[INFO] Leverage set to x{leverage} for {symbol}")
        except Exception as e:
            print(f"[WARNING] Could not set leverage: {e}. Attempting to proceed.")


        # ✅ Place market order
        order = await exchange.create_market_order(
            symbol=symbol,
            side=side,
            amount=float(qty_rounded), # Ensure amount is float for create_market_order
            params={
                'openType': 1,
                'positionType': 1 if side == 'buy' else 2
            }
        )

        print(f"[SUCCESS] Trade executed: {side.upper()} {qty_rounded} {symbol} with x{leverage} leverage")
        print(f"[ORDER INFO] Order ID: {order.get('id')}, Status: {order.get('status')}")


    except Exception as e:
        print(f"[ERROR] Trade failed: {e}")
        # Improve error details for CCXT exceptions
        if isinstance(e, ccxt.NetworkError):
            print("[DETAILS] Network error: Please check your internet connection or MEXC API status.")
        elif isinstance(e, ccxt.ExchangeError):
            print(f"[DETAILS] Exchange error: {e.args[0] if e.args else 'No specific message.'}")
        elif isinstance(e, ccxt.ArgumentsRequired):
             print(f"[DETAILS] Missing arguments for CCXT call: {e}")
        elif hasattr(e, 'args') and isinstance(e.args[0], dict):
            print("[DETAILS]", e.args[0])


client.run(DISCORD_BOT_TOKEN)
