import os
import re
import json
import asyncio
import logging
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))  # ✅ Keep as int
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", 100))
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", 5))

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

class BitgetAPI:
    BASE_URL = "https://api.bitget.com"

    def __init__(self, api_key, api_secret, passphrase):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase

    async def _signed_request(self, method, path, payload=None):
        async with aiohttp.ClientSession() as session:
            url = f"{self.BASE_URL}{path}"
            headers = {
                "ACCESS-KEY": self.api_key,
                "ACCESS-PASSPHRASE": self.passphrase,
                "Content-Type": "application/json"
            }
            async with session.request(method, url, headers=headers, json=payload) as resp:
                return await resp.json()

    async def place_order(self, symbol, side, leverage, entry_price, stop_loss, take_profits):
        await self._signed_request("POST", "/api/mix/v1/account/setLeverage", {
            "symbol": symbol,
            "marginCoin": "USDT",
            "leverage": str(leverage),
            "holdSide": side.lower()
        })

        order = await self._signed_request("POST", "/api/mix/v1/order/placeOrder", {
            "symbol": symbol,
            "marginCoin": "USDT",
            "size": TRADE_AMOUNT,
            "side": side.lower(),
            "orderType": "market",
            "price": "",
            "tradeSide": "open"
        })

        logging.info(f"Order response: {order}")
        return order

def parse_signal(content):
    try:
        lines = content.splitlines()
        symbol_line = [l for l in lines if re.match(r'^[A-Z]+USDT', l)][0]
        symbol = symbol_line.strip().replace("(SHORT)", "").strip()
        direction = "SHORT" if "(SHORT)" in symbol_line.upper() else "LONG"
        buyzone = re.findall(r"(?:BUYZONE|SELLZONE)\s+([\d\.]+)\s*-\s*([\d\.]+)", content, re.IGNORECASE)
        targets_raw = re.search(r"TARGETS\s*((?:\s*[\d\.]+\s*)+)", content, re.IGNORECASE)
        stop = re.search(r"STOP\s*([\d\.]+)", content, re.IGNORECASE)
        leverage = re.search(r"LEVERAGE\s*x?(\d+)", content, re.IGNORECASE)

        entry_zone = tuple(map(float, buyzone[0])) if buyzone else (None, None)
        targets = [float(t) for t in re.findall(r"[\d\.]+", targets_raw.group(1))] if targets_raw else []
        stop_val = float(stop.group(1)) if stop else None
        lev = int(leverage.group(1)) if leverage else DEFAULT_LEVERAGE

        return {
            "symbol": symbol,
            "direction": direction,
            "buyzone": entry_zone,
            "targets": targets[:4],
            "stop": stop_val,
            "leverage": lev
        }
    except Exception as e:
        logging.error(f"Failed to parse signal: {e}")
        return None

async def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        })

@bot.event
async def on_ready():
    logging.info(f"✅ Bot connected as {bot.user}")

@bot.event
async def on_message(message):
    if message.channel.id != SOURCE_CHANNEL_ID:
        return
    if message.author.bot:
        return

    parsed = parse_signal(message.content)
    if not parsed:
        logging.info("No valid trade signal detected.")
        return

    direction = parsed['direction']
    symbol = parsed['symbol']
    side = "open_long" if direction == "LONG" else "open_short"
    leverage = parsed['leverage']
    entry_zone = parsed['buyzone']
    targets = parsed['targets']
    stop = parsed['stop']

    alert_msg = (
        f"📊 TRADE SIGNAL RECEIVED 📊\n"
        f"Pair: {symbol}\n"
        f"Direction: {direction}\n"
        f"Buy Zone: {entry_zone[0]} - {entry_zone[1]}\n"
        f"Targets: {targets}\n"
        f"Stop Loss: {stop}\n"
        f"Leverage: x{leverage}"
    )
    await send_telegram_alert(alert_msg)

    bitget = BitgetAPI(BITGET_API_KEY, BITGET_API_SECRET, BITGET_API_PASSPHRASE)
    await bitget.place_order(symbol, side, leverage, entry_zone[0], stop, targets)

bot.run(DISCORD_BOT_TOKEN)
