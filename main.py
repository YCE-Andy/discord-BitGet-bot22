from dotenv import load_dotenv
import os
import discord
import re
import time
import hmac
import hashlib
import requests
import json

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
BLOFIN_API_KEY = os.getenv("BLOFIN_API_KEY")
BLOFIN_API_SECRET = os.getenv("BLOFIN_API_SECRET")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT"))
LEVERAGE = int(os.getenv("LEVERAGE"))

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def sign_blofin_request(api_secret, timestamp, method, path, body=''):
    payload = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

def place_market_order(symbol, leverage, size, tp_price, sl_price):
    endpoint = "/api/v1/trade/order"
    url = f"https://api.blofin.com{endpoint}"
    timestamp = str(int(time.time() * 1000))

    body = {
        "instId": symbol,
        "marginMode": "isolated",
        "positionSide": "net",
        "side": "buy",
        "orderType": "market",
        "price": "",  # required by API, but ignored for market orders
        "size": str(size),
        "reduceOnly": False,
        "clientOrderId": f"gpt-{timestamp}",
        "tpTriggerPrice": str(tp_price),
        "tpOrderPrice": "-1",
        "slTriggerPrice": str(sl_price),
        "slOrderPrice": "-1"
    }

    body_json = json.dumps(body)
    signature = sign_blofin_request(BLOFIN_API_SECRET, timestamp, "POST", endpoint, body_json)

    headers = {
        "ApiKey": BLOFIN_API_KEY,
        "Request-Time": timestamp,
        "Signature": signature,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, data=body_json)
        print("💬 BloFin response:", response.text)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

@client.event
async def on_ready():
    print(f"✅ Bot is online: {client.user}")

@client.event
async def on_message(message):
    try:
        if message.author == client.user:
            return

        if message.channel.id != DISCORD_CHANNEL_ID:
            print("⚠️ Message from another channel ignored.")
            return

        print(f"📨 Received: {message.content}")

        content = message.content.upper()

        # Parse fields
        symbol_match = re.search(r"([A-Z]+USDT)", content)
        targets = re.findall(r"\b0\.\d{3,}\b", content)
        stop_match = re.search(r"STOP\s+([\d.]+)", content)
        lev_match = re.search(r"LEVERAGE\s*x?(\d+)", content)

        if not all([symbol_match, targets, stop_match, lev_match]):
            await message.channel.send("⚠️ Could not parse trade command.")
            return

        symbol = symbol_match.group(1)
        tp_price = float(targets[0])  # Use first TP only
        sl_price = float(stop_match.group(1))
        leverage = int(lev_match.group(1))

        size = round((TRADE_AMOUNT * leverage) / tp_price, 3)

        order_result = place_market_order(symbol, leverage, size, tp_price, sl_price)

        if order_result.get("code") == "0":
            await message.channel.send(f"✅ Trade placed for {symbol} with TP {tp_price} / SL {sl_price}")
        else:
            await message.channel.send(f"❌ Trade Failed: {order_result}")
    except Exception as e:
        await message.channel.send(f"❌ Bot Error: {str(e)}")
        print("‼️ Exception:", str(e))

client.run(DISCORD_TOKEN)
