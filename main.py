import os
import time
import hmac
import json
import hashlib
import requests
import discord
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE", "")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "200"))
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# ---- SIGNING ----
def sign_bitget_request(secret, timestamp, method, path, body=''):
    """Generate Bitget signature."""
    pre_hash = f"{timestamp}{method.upper()}{path}{body}"
    signature = hmac.new(secret.encode(), pre_hash.encode(), hashlib.sha256).hexdigest()
    return signature

# ---- ORDER PLACEMENT ----
def place_futures_order(symbol, side, quantity, leverage):
    """Place a futures market order on Bitget."""
    base_url = "https://api.bitget.com"
    path = "/api/v2/mix/order/place-order"
    url = base_url + path
    timestamp = str(int(time.time() * 1000))

    side = side.lower()  # 'buy' or 'sell'
    order_type = "market"  # We use market orders

    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": str(quantity),
        "side": side,
        "orderType": order_type,
        "force": "gtc",
        "leverage": str(leverage)
    }

    body_str = json.dumps(body, separators=(',', ':'))
    signature = sign_bitget_request(BITGET_SECRET_KEY, timestamp, "POST", path, body_str)

    headers = {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

    try:
        print(f"📤 Sending Bitget Order: {body}")
        response = requests.post(url, headers=headers, data=body_str, timeout=30)
        print(f"📥 Bitget Response: {response.text}")
        return response.json()
    except Exception as e:
        print(f"⚠️ Bitget request error: {e}")
        return {"error": str(e)}

# ---- DISCORD BOT EVENTS ----
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id != ALERT_CHANNEL_ID:
        print(f"🟨 Message ignored: Wrong channel ({message.channel.id})")
        return

    content = message.content.upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        await message.channel.send("🟨 Message received")
        try:
            parts = content.split()
            raw_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = raw_symbol + "USDT_UMCBL"  # Bitget USDT-margined perpetual format
            side = "buy"
            leverage = DEFAULT_LEVERAGE

            if "LEVERAGE" in parts:
                i = parts.index("LEVERAGE")
                try:
                    leverage = int(parts[i + 1].replace("X", ""))
                except:
                    pass

            i = parts.index("BUYZONE")
            entry_low = float(parts[i + 1])
            if parts[i + 2] == "-":
                entry_high = float(parts[i + 3])
            else:
                entry_high = float(parts[i + 2])

            entry_price = (entry_low + entry_high) / 2
            quantity = round(TRADE_AMOUNT / entry_price, 2)

            await message.channel.send(f"🔎 Parsed symbol: {symbol}")
            await message.channel.send(f"⚙️ Leverage detected: x{leverage}")
            await message.channel.send(f"💰 Entry price: {entry_price}")
            await message.channel.send(f"📦 Quantity: {quantity}")

            result = place_futures_order(symbol, side, quantity, leverage)

            if result.get("code") == "00000":
                await message.channel.send(f"✅ Trade Executed: {symbol} x{leverage}")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")

            await asyncio.sleep(1)

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

# Run the bot
client.run(DISCORD_BOT_TOKEN)
