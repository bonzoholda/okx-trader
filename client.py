import time
import json
import base64
import hmac
import hashlib
import requests
from datetime import datetime
from config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE, OKX_BASE_URL, SYMBOL
import os

class OKXClient:



    print(f"OKX API Key: {os.environ.get('OKX_API_KEY')}")
    print(f"OKX API Secret: {os.environ.get('OKX_SECRET_KEY')}")
    print(f"OKX API Passphrase: {os.environ.get('OKX_PASSPHRASE')}")

    
    def __init__(self):
        self.api_key = OKX_API_KEY
        self.api_secret = OKX_SECRET_KEY
        self.api_passphrase = OKX_PASSPHRASE
        self.base_url = OKX_BASE_URL

        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json"
        })

    def _get_timestamp(self):
        return datetime.utcnow().isoformat("T", "milliseconds") + "Z"

    def _sign(self, timestamp, method, request_path, body=""):
        method = method.upper()
        message = f"{timestamp}{method}{request_path}{body}"
        mac = hmac.new(self.api_secret.encode(), message.encode(), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode()


    def _auth_headers(self, timestamp, method, path, body=""):
        sign = self._sign(timestamp, method, path, body)
        return {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.api_passphrase,
            "Content-Type": "application/json"
        }

    def _request(self, method, path, params=None, body=None):
        url = self.base_url + path
        body_json = json.dumps(body) if body else ""

        headers = self._auth_headers(method, path, body_json)

        try:
            if method == "GET":
                response = self.session.get(url, headers=headers, params=params)
            else:
                response = self.session.request(method, url, headers=headers, data=body_json)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[ERROR] API request failed: {e}")
            return None

    # === PUBLIC API ===
    def get_price(self):
        response = self._request("GET", "/api/v5/market/ticker", params={"instId": SYMBOL})
        if response and response.get("data"):
            return float(response["data"][0]["last"])
        return None

    # === PRIVATE APIs ===
    def get_balance(self, currency):
        method = "GET"
        path = f"/api/v5/account/balance?ccy={currency}"
        url = self.base_url + path
        headers = self._auth_headers(method, path)

        try:
            res = self.session.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()

            # For debugging
            print(f"[DEBUG] Raw balance data for {currency}: {json.dumps(data, indent=2)}")

            details = data["data"][0].get("details", [])
            for item in details:
                if item["ccy"] == currency:
                    return float(item["availBal"])
            return 0.0
        except Exception as e:
            print(f"[ERROR] Balance fetch failed: {e}")
            return 0.0


    def place_order(self, side, amount):
        order_type = "buy" if side == "long" else "sell"
        body = {
            "instId": SYMBOL,
            "tdMode": "cash",
            "side": order_type,
            "ordType": "market",
            "sz": str(amount),
        }
        return self._request("POST", "/api/v5/trade/order", body=body)

    def get_position_size(self, currency):
        return self.get_balance(currency)

    def test_connection(self):
        try:
            print("[INFO] Testing OKX API credentials...")
    
            # Simulate a simple request to get the balance
            method = "GET"
            path = "/api/v5/account/balance?ccy=USDT"  # The correct API path for balance
            body = ""
    
            # We call _auth_headers with the required arguments
            headers = self._auth_headers(method, path, body)
            
            # Send a request using the headers to test connection
            response = self.session.get(self.base_url + path, headers=headers)
            response.raise_for_status()
    
            # If everything is fine, parse and return balance
            data = response.json()
            available_balance = float(data["data"][0]["details"][0]["availBal"])
            print(f"[SUCCESS] API credentials are working. Available USDT balance: {available_balance}")
    
        except Exception as e:
            print(f"[FAILURE] API credentials test failed: {e}")




