import ccxt

exchange = ccxt.mexc({
    'options': {
        'defaultType': 'swap',  # Use USDT-M futures
    }
})

exchange.load_markets()

symbol = "MANA/USDT:USDT"

if symbol in exchange.markets:
    print(f"✅ {symbol} is available on MEXC futures")
else:
    print(f"❌ {symbol} is NOT available on MEXC futures")
