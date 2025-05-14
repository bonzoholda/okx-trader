import time
import json
import base64
import hmac
import hashlib
import requests
from datetime import datetime
from config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE, OKX_BASE_URL, SYMBOL
import os
import okx.Account as Account

# Set flag to "0" for live trading or "1" for demo trading
flag = "0"

# Initialize the Account API client
accountAPI = Account.AccountAPI(OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE, False, flag)

class OKXClient:
    def __init__(self):
        self.api_key = OKX_API_KEY
        self.api_secret = OKX_SECRET_KEY
        self.api_passphrase = OKX_PASSPHRASE
        self.base_url = OKX_BASE_URL

        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json"
        })

    def test_connection(self):
        try:
            # Fetch balance info using get_balance instead of get_account_assets
            result = accountAPI.get_balance()
            
            # Print the result
            print(result)
            
            # Check if API credentials are working
            if result and result.get("code") == "0":
                print("[INFO] API credentials are working.")
                
                # Parse and print asset balances
                for asset in result['data']:
                    print(f"Asset: {asset['coin']}, Available Balance: {asset['available']}")
                
                return True
            else:
                print("[ERROR] API credentials test failed.")
                return False
        except Exception as e:
            print(f"[ERROR] Test connection failed: {e}")
            return False

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
        headers = self._auth_headers(self._get_timestamp(), method, path, body_json)  # Fix this call

        try:
            if method == "GET":
                response = self.session.get(url, params=params, headers=headers)
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
        headers = self._auth_headers(self._get_timestamp(), method, path)  # Fix this call

        try:
            res = self.session.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()

            # For debugging
            #print(f"[DEBUG] Raw balance data for {currency}: {json.dumps(data, indent=2)}")

            details = data["data"][0].get("details", [])
            for item in details:
                if item["ccy"] == currency:
                    return float(item["availBal"])
            return 0.0
        except Exception as e:
            print(f"[ERROR] Balance fetch failed: {e}")
            return 0.0

    def place_order(self, side, amount):
        print(f"[DEBUG] Placing order: side={side}, amount={amount}")
    
        body = {
            "instId": SYMBOL,
            "tdMode": "cash",
            "side": "buy" if side == "long" else "sell",
            "ordType": "market",
            "sz": str(amount),
        }
    
        response = self._request("POST", "/api/v5/trade/order", body=body)
        print(f"[DEBUG] API response: {response}")
        return response


    def get_position_size(self, currency):
        return self.get_balance(currency)
