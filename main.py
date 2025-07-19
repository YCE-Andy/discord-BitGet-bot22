import os
import time
import hmac
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv()

# Load Bitget API credentials
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

def sign_bitget_request(secret, timestamp, method, path, body=''):
    """
    Bitget signature: HMAC_SHA256(timestamp + method + path + body)
    """
    raw = f"{timestamp}{method.upper()}{path}{body}"
    print("🔐 Raw string to sign:")
    print(raw)
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()

def test_bitget_auth():
    timestamp = str(int(time.time() * 1000))
    path = "/api/v2/mix/account/accounts"
    query = "?productType=umcbl"
    full_path = path + query
    url = f"https://api.bitget.com{full_path}"

    method = "GET"
    body = ""
    signature = sign_bitget_request(BITGET_SECRET_KEY, timestamp, method, full_path, body)

    headers = {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

    print("\n📤 Sending request to Bitget...")
    print(f"➡️ URL: {url}")
    print(f"➡️ Headers: {headers}")

    try:
        response = requests.get(url, headers=headers)
        print("\n📥 Bitget Response:")
        print(response.status_code)
        print(response.text)
    except Exception as e:
        print(f"❌ Request error: {e}")

# 🔧 Run test
test_bitget_auth()
