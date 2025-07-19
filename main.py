import os
import time
import hmac
import json
import hashlib
import requests
import discord
import asyncio

# Environment variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "200"))
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))

BITGET_API_URL = "https://api.bitget.com"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# Signature generator
def generate_signature(timestamp, method, path, body):
    if body == "{}":
        body = ""  # Bitget requires empty string for empty body
    pre_hash = f"{timestamp}{method.upper()}{path}{body}"
    signature = hmac.new(
        BITGET_SECRET_KEY.encode(),
        pre_hash.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature

# Header builder
def get_headers(method, path, body):
    timestamp = str(int(time.time() * 1000))
    sign = generate_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

# Order sender
def place_futures_order(symbol, side, quantity, leverage):
    path = "/api/v2/mix/order/place-order"
    url = BITGET_API_URL + path

    payload = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": "buy" if side.lower() == "buy" else "sell",
        "orderType": "market",
        "size": str(quantity),
        "leverage": str(leverage),
        "productType": "umcbl",
        "marginMode": "isolated"
    }

    body_str = json.dumps(payload, separators=(",", ":"))
    headers = get_headers("POST", path, body_str)

    try:
        print(f"📤 Sending order: {body_str}")
        response = requests.post(url, headers=headers, data=body_str)
        print(f"📥 Response: {response.text}")
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# On ready
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

# On message (trade relay logic)
@client.event
async def on_message(message):
    if message.author.bot or message.channel.id != ALERT_CHANNEL_ID:
        return

    content = message.content.upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        await message.channel.send("🟨 Trade signal received")
        try:
            parts = content.split()
            raw_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = f"{raw_symbol}USDT"
            side = "buy"
            leverage = DEFAULT_LEVERAGE

            if "LEVERAGE" in parts:
                try:
                    lev_index = parts.index("LEVERAGE")
                    leverage = int(parts[lev_index + 1].replace("X", ""))
                except:
                    pass

            i = parts.index("BUYZONE")
            entry_low = float(parts[i + 1])
            entry_high = float(parts[i + 3]) if parts[i + 2] == "-" else float(parts[i + 2])
            entry_price = (entry_low + entry_high) / 2
            quantity = round(TRADE_AMOUNT / entry_price, 3)

            await message.channel.send(f"🔎 Symbol: `{symbol}`")
            await message.channel.send(f"⚙️ Leverage: `{leverage}`")
            await message.channel.send(f"💰 Entry: `{entry_price}`")
            await message.channel.send(f"📦 Quantity: `{quantity}`")

            result = place_futures_order(symbol, side, quantity, leverage)

            if result.get("code") == "00000":
                await message.channel.send(f"✅ Trade executed: `{symbol}` x{leverage}")
            else:
                await message.channel.send(f"❌ Trade Failed:\n```{json.dumps(result, indent=2)}```")

        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

# Start bot
client.run(DISCORD_BOT_TOKEN)
