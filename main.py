import os
import time
import hmac
import json
import hashlib
import base64
import requests
import discord
import asyncio

# Load environment variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))
TRADE_RISK_PERCENT = 0.2  # 20%

BITGET_API_URL = "https://api.bitget.com"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

def generate_signature(timestamp, method, request_path, body):
    pre_hash = f"{timestamp}{method.upper()}{request_path}{body}"
    hmac_digest = hmac.new(
        BITGET_SECRET_KEY.encode(),
        pre_hash.encode(),
        hashlib.sha256
    ).digest()
    return base64.b64encode(hmac_digest).decode()

def get_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    sign = generate_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_usdt_balance():
    path = "/api/v2/mix/account/account"
    url = BITGET_API_URL + path
    params = {"productType": "umcbl"}
    headers = get_headers("GET", path)
    try:
        res = requests.get(url, headers=headers, params=params)
        data = res.json()
        for asset in data.get("data", []):
            if asset.get("marginCoin") == "USDT":
                return float(asset.get("available"))
    except Exception as e:
        print(f"⚠️ Error fetching balance: {e}")
    return 0.0

symbol_meta_cache = {}

def get_symbol_meta(symbol):
    global symbol_meta_cache
    symbol = symbol.strip().upper()

    if symbol in symbol_meta_cache:
        return symbol_meta_cache[symbol]

    try:
        path = "/api/v2/mix/market/symbols"
        url = BITGET_API_URL + path + "?productType=umcbl"
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()

        for item in data.get("data", []):
            item_symbol = item.get("symbol", "").strip().upper()
            if item_symbol == symbol:
                symbol_meta_cache[symbol] = item
                return item

        print(f"⚠️ Symbol {symbol} not found in Bitget symbols.")
        return None

    except Exception as e:
        print(f"❌ Error fetching symbol metadata: {e}")
        return None

def round_size(size, precision):
    factor = 10 ** precision
    return int(size * factor) / factor

def place_futures_order(symbol, side, quantity, leverage):
    path = "/api/v2/mix/order/place-order"
    url = BITGET_API_URL + path
    body_data = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": side,
        "orderType": "market",
        "size": str(quantity),
        "leverage": str(leverage),
        "productType": "umcbl",
        "marginMode": "isolated"
    }
    body_json = json.dumps(body_data)
    headers = get_headers("POST", path, body_json)
    try:
        res = requests.post(url, headers=headers, json=body_data)
        return res.json()
    except Exception as e:
        print(f"⚠️ Order error: {e}")
        return {"error": "Order failed."}

def place_tp_sl_orders(symbol, side, base_quantity, targets, stop_price):
    tp_percents = [0.5, 0.2, 0.15, 0.1, 0.05]
    tp_qtys = [round_size(base_quantity * p, 4) for p in tp_percents]
    tp_side = "sell" if side == "buy" else "buy"
    orders = []

    for i in range(min(5, len(targets))):
        body = {
            "symbol": symbol,
            "marginCoin": "USDT",
            "side": tp_side,
            "orderType": "limit",
            "price": str(targets[i]),
            "size": str(tp_qtys[i]),
            "marginMode": "isolated",
            "productType": "umcbl",
            "reduceOnly": True
        }
        body_json = json.dumps(body)
        headers = get_headers("POST", "/api/v2/mix/order/place-order", body_json)
        try:
            res = requests.post(BITGET_API_URL + "/api/v2/mix/order/place-order", headers=headers, json=body)
            orders.append(res.json())
        except Exception as e:
            print(f"⚠️ TP/SL order failed: {e}")
    return orders

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot or message.channel.id != ALERT_CHANNEL_ID:
        return

    content = message.content.upper()
    if "BUYZONE" in content and "TARGETS" in content and "STOP" in content:
        await message.channel.send("🟨 Signal received")
        try:
            parts = content.split()
            raw_symbol = parts[0].replace("PERP", "").replace("USDT", "")
            symbol = f"{raw_symbol}USDT"

            side = "buy"
            if "SHORT" in parts[0] or "(SHORT)" in content:
                side = "sell"

            leverage = DEFAULT_LEVERAGE
            if "LEVERAGE" in parts:
                i = parts.index("LEVERAGE")
                try:
                    leverage = int(parts[i + 1].replace("X", ""))
                except:
                    pass

            i = parts.index("BUYZONE")
            entry_low = float(parts[i + 1].replace("–", "-"))
            entry_high = float(parts[i + 3]) if parts[i + 2] == "-" else float(parts[i + 2])
            entry_price = (entry_low + entry_high) / 2

            targets = []
            target_index = parts.index("TARGETS") + 1
            for j in range(target_index, len(parts)):
                if parts[j] == "STOP":
                    break
                try:
                    targets.append(float(parts[j]))
                except:
                    continue

            stop_price = float(parts[parts.index("STOP") + 1])
            balance = get_usdt_balance()
            trade_amount = balance * TRADE_RISK_PERCENT

            meta = get_symbol_meta(symbol)
            if not meta:
                await message.channel.send(f"⚠️ Symbol metadata not found for {symbol}")
                return

            size_precision = int(meta.get("pricePlace", 3))
            quantity = round_size(trade_amount / entry_price, size_precision)

            await message.channel.send(f"🔎 Symbol: {symbol}")
            await message.channel.send(f"📈 Side: {'LONG' if side == 'buy' else 'SHORT'}")
            await message.channel.send(f"⚙️ Leverage: x{leverage}")
            await message.channel.send(f"💰 Entry: {entry_price}, Qty: {quantity}")

            result = place_futures_order(symbol, side, quantity, leverage)
            if result.get("code") == "00000":
                await message.channel.send(f"✅ Order Placed. Adding TP/SL...")
                tp_result = place_tp_sl_orders(symbol, side, quantity, targets, stop_price)
                await message.channel.send(f"🎯 TP/SL orders sent.")
            else:
                await message.channel.send(f"❌ Trade Failed: {result}")
        except Exception as e:
            await message.channel.send(f"⚠️ Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
