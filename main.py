import os
import time
import hmac
import json
import hashlib
import base64
import requests
import discord

# ENV Vars
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALERT_CHANNEL_ID = int(os.getenv("ALERT_CHANNEL_ID"))

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))
TRADE_RISK = 0.2  # 20% of balance

BITGET_API_URL = "https://api.bitget.com"

# Discord client
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# Signature Helpers
def generate_signature(ts, method, path, body):
    pre = f"{ts}{method.upper()}{path}{body}"
    dig = hmac.new(BITGET_SECRET_KEY.encode(), pre.encode(), hashlib.sha256).digest()
    return base64.b64encode(dig).decode()

def get_headers(method, path, body=""):
    ts = str(int(time.time() * 1000))
    return {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": generate_signature(ts, method, path, body),
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

# Fetch USDT balance
def get_balance():
    r = requests.get(
        BITGET_API_URL + "/api/v2/mix/account/account",
        headers=get_headers("GET", "/api/v2/mix/account/account")
    ).json()
    for a in r.get("data", []):
        if a.get("marginCoin") == "USDT":
            return float(a.get("available", 0))
    return 0

# Place market order
def place_market(symbol, side, qty, lev):
    path = "/api/v2/mix/order/place-order"
    body = json.dumps({
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": side,
        "orderType": "market",
        "size": str(qty),
        "leverage": str(lev),
        "productType": "umcbl",
        "marginMode": "isolated"
    })
    return requests.post(BITGET_API_URL + path, headers=get_headers("POST", path, body), data=body).json()

# Place TP & SL
def place_tp_sl(symbol, side, qty, targets, stop):
    results = []
    opp = "sell" if side == "buy" else "buy"
    tp_ratios = [0.5, 0.2, 0.15, 0.1, 0.05]
    for i, t in enumerate(targets[:5]):
        results.append(requests.post(
            BITGET_API_URL + "/api/v2/mix/order/place-order",
            headers=get_headers("POST", "/api/v2/mix/order/place-order", ""),
            json={
                "symbol": symbol,
                "marginCoin": "USDT",
                "side": opp,
                "orderType": "limit",
                "price": str(t),
                "size": str(round(qty * tp_ratios[i], 4)),
                "marginMode": "isolated",
                "productType": "umcbl",
                "reduceOnly": True
            }
        ).json())
    # Stop-market
    results.append(requests.post(
        BITGET_API_URL + "/api/v2/mix/plan/place-plan",
        headers=get_headers("POST", "/api/v2/mix/plan/place-plan", ""),
        json={
            "symbol": symbol,
            "marginCoin": "USDT",
            "side": opp,
            "orderType": "market",
            "triggerPrice": str(stop),
            "triggerType": "fill_price",
            "size": str(qty),
            "marginMode": "isolated",
            "productType": "umcbl"
        }
    ).json())
    return results

# Discord events
@client.event
async def on_ready():
    print("Bot ready.")

@client.event
async def on_message(msg):
    if msg.author.bot or msg.channel.id != ALERT_CHANNEL_ID:
        return

    c = msg.content.upper().replace("–", "-")
    if "BUYZONE" in c and "TARGETS" in c and "STOP" in c:
        await msg.channel.send("🟨 Signal received")
        parts = c.split()
        sym = parts[0].replace("PERP", "").replace("USDT", "") + "USDT"
        side = "buy" if "SHORT" not in parts[0] else "sell"
        lev = DEFAULT_LEVERAGE
        if "LEVERAGE" in parts:
            try: lev = int(parts[parts.index("LEVERAGE") + 1].replace("X", ""))
            except: pass

        i = parts.index("BUYZONE")
        low = float(parts[i+1]); high = float(parts[i+3] if parts[i+2]=="-" else parts[i+2])
        entry = (low + high) / 2

        tstart = parts.index("TARGETS") + 1
        targets = [float(v) for v in parts[tstart:parts.index("STOP")] if v.replace('.', '',1).isdigit()]

        stop = float(parts[parts.index("STOP") + 1])
        bal = get_balance()
        qty = round((bal * TRADE_RISK) / entry, 4)

        await msg.channel.send(f"Entry: {sym} qty={qty}@{entry} lev={lev}")
        res = place_market(sym, side, qty, lev)
        await msg.channel.send(f"Market res: {res}")

        if res.get("code") == "00000":
            resp = place_tp_sl(sym, side, qty, targets, stop)
            await msg.channel.send(f"TP/SL orders: {resp}")
        else:
            await msg.channel.send("❌ Entry failed, skipping TP/SL")

client.run(DISCORD_BOT_TOKEN)
