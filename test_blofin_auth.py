import os
import requests
import time
import hmac
import hashlib
import base64

API_KEY = os.getenv("BITGET_API_KEY")  # still using these env vars for BloFin
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

base_url = "https://api.blofin.com"
endpoint = "/api/v1/account/balance"
method = "GET"

def sign(timestamp, method, request_path, body):
    prehash = f"{timestamp}{method.upper()}{request_path}{body}"
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        prehash.encode("utf-8"),
        hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode()

timestamp = str(int(time.time() * 1000))
body = ""
signature = sign(timestamp, method, endpoint, body)

headers = {
    "ACCESS-KEY": API_KEY,
    "ACCESS-SIGN": signature,
    "ACCESS-TIMESTAMP": timestamp,
    "ACCESS-PASSPHRASE": PASSPHRASE,
    "Content-Type": "application/json"
}

url = base_url + endpoint
response = requests.get(url, headers=headers)

try:
    data = response.json()
    print("✅ Response from BloFin:")
    print(data)
except Exception as e:
    print("❌ Invalid JSON response:")
    print(response.text)
