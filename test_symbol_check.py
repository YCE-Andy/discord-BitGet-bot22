import requests

symbol = "MANAUSDT_UMCBL"  # Bitget futures symbol format

url = "https://api.bitget.com/api/v2/mix/market/contracts?productType=umcbl"

response = requests.get(url)
data = response.json()

available_symbols = [item["symbol"] for item in data["data"]]

if symbol in available_symbols:
    print(f"✅ {symbol} is available on Bitget USDT futures")
else:
    print(f"❌ {symbol} is NOT available on Bitget USDT futures")
