import os
import discord
import re
import requests
import json
from decimal import Decimal, ROUND_DOWN

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
DISCORD_RELAY_CHANNEL_ID = int(os.getenv("DISCORD_RELAY_CHANNEL_ID"))
TRADE_AMOUNT_USDT = Decimal(os.getenv("TRADE_AMOUNT", "200"))
DEFAULT_LEVERAGE = int(os.getenv("LEVERAGE", "5"))

API_URL = "https://api.bitget.com"
HEADERS = {
    'Content-Type': 'application/json',
    'ACCESS-KEY': BITGET_API_KEY,
    'ACCESS-PASSPHRASE': BITGET_API_PASSPHRASE,
    # Normally you'd also include signature headers here, but skipping for now.
}

def extract_trade_details(message):
    try:
        lines = message.content.splitlines()
        symbol_line = next(line for line in lines if re.search(r'USDT', line, re.IGNORECASE))
        side = 'buy' if '(SHORT)' not in symbol_line.upper() else 'sell'

        match_symbol = re.search(r'(\w+USDT)', symbol_line.upper())
        symbol = match_symbol.group(1) if match_symbol else None

        buyzone = next(line for line in lines if 'BUYZONE' in line.upper() or 'SELLZONE' in line.upper())
        targets_index = lines.index(next(line for line in lines if 'TARGETS' in line.upper()))
        targets = [float(lines[i]) for i in range(targets_index+1, targets_index+6) if re.match(r'^\d+\.\d+', lines[i])]

        stop_line = next(line for line in lines if 'STOP' in line.upper())
        stop_price = float(re.search(r'\d+\.\d+', stop_line).group())

        leverage_line = next((line for line in lines if 'LEVERAGE' in line.upper()), None)
        leverage = int(re.search(r'x(\d+)', leverage_line).group(1)) if leverage_line else DEFAULT_LEVERAGE

        return {
            'symbol': symbol,
            'side': side,
            'targets': targets,
            'stop_price': stop_price,
            'leverage': leverage
        }
    except Exception as e:
        print(f"❌ Error extracting trade details: {e}")
        return None

def place_market_order(trade):
    url = f"{API_URL}/api/v2/mix/order/place-order"
    payload = {
        "symbol": trade['symbol'] + "_UMCBL",
        "marginCoin": "USDT",
        "size": "0.05",  # Just placeholder, usually this should be based on market precision
        "side": trade['side'],
        "orderType": "market",
        "force": "gtc",
    }
    response = requests.post(url, headers=HEADERS, data=json.dumps(payload))
    return response.json()

def place_plan_order(symbol, trigger_price, order_price, side, plan_type):
    url = f"{API_URL}/api/v2/mix/order/place-plan-order"
    payload = {
        "symbol": symbol + "_UMCBL",
        "marginCoin": "USDT",
        "size": "0.05",  # Placeholder
        "side": side,
        "orderType": "limit",
        "triggerPrice": str(trigger_price),
        "executePrice": str(order_price),
        "triggerType": "mark_price",
        "planType": plan_type,
        "marginMode": "isolated",
        "productType": "umcbl"
    }
    response = requests.post(url, headers=HEADERS, data=json.dumps(payload))
    return response.json()

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.channel.id != DISCORD_RELAY_CHANNEL_ID:
        return
    if not any(keyword in message.content.upper() for keyword in ['BUYZONE', 'SELLZONE']):
        return

    trade = extract_trade_details(message)
    if not trade:
        return

    confirmation = f"🟨 Signal received\n"
    order_result = place_market_order(trade)

    if order_result.get('code') == '00000':
        confirmation += f"✅ Bitget Order Placed: {trade['symbol']} x{trade['leverage']} [{'BUY' if trade['side']=='buy' else 'SELL'}]\n"
        
        # Place TP
        for target in trade['targets']:
            tp_result = place_plan_order(trade['symbol'], target, target, 'sell' if trade['side'] == 'buy' else 'buy', 'profit_plan')
            confirmation += f"📈 TP @{target}: {tp_result}\n"

        # Place SL
        sl_result = place_plan_order(trade['symbol'], trade['stop_price'], trade['stop_price'], 'sell' if trade['side'] == 'buy' else 'buy', 'loss_plan')
        confirmation += f"🛑 SL @{trade['stop_price']}: {sl_result}\n"
    else:
        confirmation += f"❌ Trade Failed: {order_result}\n"

    await message.channel.send(confirmation)

client.run(os.getenv("DISCORD_BOT_TOKEN"))
