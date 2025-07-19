import os
import time
import hmac
import hashlib
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get keys from env
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

def sign_bitget_request(secret, timestamp, method, path, body=''):
    pre_hash = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(secret.encode(), pre_hash.encode(), hashlib.sha256).hexdigest()

def test_bitget_auth():
    url = "https://api.bitget.com/api/v2/mix/account/accounts?productType=umcbl"
    timestamp = str(int(time.time() * 1000))
    path = "/api/v2/mix/account/accounts"
    query = "?productType=umcbl"
    signature = sign_bitget_request(BITGET_SECRET_KEY, timestamp, "GET", path + query)

    headers = {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE
    }

    response = requests.get(url, headers=headers)
    print(f"📥 Response: {response.status_code}")
    print(response.text)

test_bitget_auth()
