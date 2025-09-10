import os
import time
import uuid
import hmac
import hashlib
import base64
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get keys from environment
BLOFIN_API_KEY       = os.getenv("BLOFIN_API_KEY")
BLOFIN_SECRET_KEY    = os.getenv("BLOFIN_SECRET_KEY")
BLOFIN_PASSPHRASE    = os.getenv("BLOFIN_PASSPHRASE")

BASE_URL = "https://openapi.blofin.com"

def sign_blofin_request(secret, method, path, body=None):
    timestamp = str(int(time.time() * 1000))
    nonce     = str(uuid.uuid4())
    prehash = f"{path}{method.upper()}{timestamp}{nonce}"
    if body:
        prehash += json.dumps(body, separators=(',', ':'))
    hex_sig = hmac.new(secret.encode(), prehash.encode(), hashlib.sha256).hexdigest().encode()
    signature = base64.b64encode(hex_sig).decode()
    return timestamp, nonce, signature

def test_blofin_auth():
    path   = "/api/v1/asset/balances?accountType=futures"
    url    = BASE_URL + path
    method = "GET"
    
    timestamp, nonce, signature = sign_blofin_request(BLOFIN_SECRET_KEY, method, path)
    
    headers = {
        "ACCESS-KEY":       BLOFIN_API_KEY,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-NONCE":     nonce,
        "ACCESS-SIGN":      signature,
        "ACCESS-PASSPHRASE": BLOFIN_PASSPHRASE
    }
    
    response = requests.get(url, headers=headers)
    print("Status Code:", response.status_code)
    print("Response:", response.text)

if __name__ == "__main__":
    test_blofin_auth()
