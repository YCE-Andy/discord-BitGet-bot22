import os
import hmac
import time
import json
import hashlib
import requests
import discord
import re
from decimal import Decimal

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
TRADE_AMOUNT = Decimal(os.getenv("TRADE_AMOUNT", "200"))

client = discord.Client(intents=discord.Intents.all())

BASE_URL = "https://api.bitget.com"

def sign_request(timestamp, method, endpoint, body):
    message = f"{timestamp}{method}{endpoint}{body}"
    mac = hmac.new(BITGET_SECRET_KEY.encode(), message.encode(), hashlib.sha256)
    return mac.hexdigest()

def place_order(symbol, side, size):
    timestamp = str(int(time.time() * 1000))
    endpoint = "/api/v2/mix/order/place-order"
    url = BASE_URL + endpoint
    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": side,
        "orderType": "market",
        "size": str(size),
        "price": "",
        "productType": "umcbl"
    }
    body_json = json.dumps(body)
    headers = {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": sign_request(timestamp, "POST", endpoint, body_json),
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, data=body_json)
    result = response.json()
    if result.get("code") == "00000":
        return result["data"]["orderId"]
    else:
        print("❌ Trade Failed:", result)
        return None

def place_tp_sl(symbol, entry_price, targets, stop, side):
    plan_endpoint = "/api/v2/mix/order/place-plan-order"
    url = BASE_URL + plan_endpoint

    for i, target in enumerate(targets[:5]):
        ratio = [0.5, 0.2, 0.15, 0.1, 0.05][i]
        trigger_price = float(target)
        order_side = "sell" if side == "buy" else "buy"
        plan_type = "profit_plan"
        timestamp = str(int(time.time() * 1000))
        body = {
            "symbol": symbol,
            "marginCoin": "USDT",
            "size": "",  # optional
            "side": order_side,
            "triggerPrice": str(trigger_price),
            "executePrice": str(trigger_price),
            "triggerType": "market_price",
            "orderType": "market",
            "planType": plan_type,
            "productType": "umcbl"
        }
        body_json = json.dumps(body)
        headers = {
            "ACCESS-KEY": BITGET_API_KEY,
            "ACCESS-SIGN": sign_request(timestamp, "POST", plan_endpoint, body_json),
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, data=body_json)
        print(f"📈 TP @{trigger_price}: {response.json()}")

    # SL
    timestamp = str(int(time.time() * 1000))
    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": "",
        "side": "sell" if side == "buy" else "buy",
        "triggerPrice": str(stop),
        "executePrice": str(stop),
        "triggerType": "market_price",
        "orderType": "market",
        "planType": "loss_plan",
        "productType": "umcbl"
    }
    body_json = json.dumps(body)
    headers = {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": sign_request(timestamp, "POST", plan_endpoint, body_json),
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers, data=body_json)
    print(f"🛑 SL @{stop}: {response.json()}")

def extract_trade_details(message):
    content = message.content.upper()
    symbol_match = re.search(r"([A-Z]+USDT)", content)
    buyzone_match = re.search(r"BUYZONE\s+([\d.]+)\s*-\s*([\d.]+)", content)
    targets_match = re.findall(r"(?<=\n| )\d+\.\d{3,6}(?=\n|$)", content)
    stop_match = re.search(r"STOP\s+([\d.]+)", content)
    leverage_match = re.search(r"LEVERAGE\s+X?(\d+)", content)

    if not (symbol_match and buyzone_match and targets_match and stop_match):
        return None

    symbol = symbol_match.group(1)
    entry = (float(buyzone_match.group(1)) + float(buyzone_match.group(2))) / 2
    targets = [float(t) for t in targets_match]
    stop = float(stop_match.group(1))
    leverage = int(leverage_match.group(1)) if leverage_match else 5

    return {
        "symbol": symbol,
        "entry": entry,
        "targets": targets,
        "stop": stop,
        "leverage": leverage,
        "side": "buy"
    }

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != ALERT_CHANNEL_ID or message.author == client.user:
        return

    if "BUYZONE" in message.content and "STOP" in message.content:
        print("🟨 Signal received")

        try:
            details = extract_trade_details(message)
            if not details:
                print("❌ Error: could not parse signal")
                return

            entry_price = details["entry"]
            symbol = details["symbol"]
            size = round(float(TRADE_AMOUNT) / entry_price, 4)

            order_id = place_order(symbol, details["side"], size)
            if order_id:
                print(f"✅ Bitget Order Placed: {symbol} x{details['leverage']} [BUY]")
                place_tp_sl(symbol, entry_price, details["targets"], details["stop"], details["side"])
        except Exception as e:
            print("❌ Error handling message:", e)

client.run(DISCORD_BOT_TOKEN)
