try:
    market = trade["symbol"]
    side = trade["side"]
    leverage = 100  # Forced leverage
    notional = 200  # Fixed USDT

    exchange.load_markets()
    market_info = exchange.market(market)
    ticker = exchange.fetch_ticker(market)
    price = ticker.get("last")

    if price is None or price <= 0:
        raise Exception(f"Invalid price: {price}")

    # Fallbacks
    precision = market_info.get("precision", {}).get("amount", 4)
    min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.0001)

    # Safe quantity calc
    raw_qty = notional / price
    quantity = round(max(raw_qty, min_qty), precision)

    if quantity <= 0:
        raise Exception(f"Invalid final quantity: {quantity} for notional {notional} and price {price}")

    print(f"🚀 Placing market order: {side.upper()} {quantity} {market} @ {price} with x{leverage}")

    order = exchange.create_market_order(
        symbol=market,
        side=side,
        amount=quantity,
        params={
            'positionSide': 'LONG' if side == 'buy' else 'SHORT',
            'leverage': leverage
        }
    )

    print(f"✅ Trade executed: {side.upper()} {quantity} {market} with x{leverage} leverage")

except Exception as e:
    print(f"❌ Error processing trade: {e}")
