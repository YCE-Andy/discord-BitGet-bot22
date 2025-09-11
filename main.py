import hmac
import hashlib
import time
import base64
import json
import requests

# ✅ Railway variables (replace these with your own for local testing)
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL = "https://api.blofin.com"

# ✅ Simplified function to place a test trade (BUY 10 contracts AIUSDT)
def place_test_trade():
    path = "/api/v1/trade/order"
    url = BASE_URL + path

    method = "POST"
    timestamp = str(int(time.time() * 1000))  # current time in ms
    
    body = {
        "instId": "AIUSDT",
        "marginMode": "isolated",
        "positionSide": "net",
        "side": "buy",
        "orderType": "market",
        "size": "10"
    }

    body_json = json.dumps(body, separators=(',', ':'))  # compact JSON

    # ✅ Signature generation
    pre_hash = timestamp + method + path + body_json
    signature = base64.b64encode(hmac.new(API_SECRET.encode(), pre_hash.encode(), hashlib.sha256).digest()).decode()

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

    # ✅ Send request
    try:
        response = requests.post(url, headers=headers, data=body_json)
        print("✅ Raw Response:", response.text)
        return response.json()  # might still fail here if .text is empty
    except Exception as e:
        return {"error": str(e)}

# Run test
if __name__ == "__main__":
    result = place_test_trade()
    print("Trade Result:", result)
