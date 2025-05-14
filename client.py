import time
import json
import base64
import hmac
import hashlib
import requests
from datetime import datetime
from config import OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE, OKX_BASE_URL, SYMBOL

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
        timestamp = self._get_timestamp()
        headers = self._auth_headers(timestamp, method, path, body_json)

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
        response = self._request("GET", f"/api/v5/account/balance", params={"ccy": currency})
        if response and response.get("data") and response["data"][0]["details"]:
            return float(response["data"][0]["details"][0]["availBal"])
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
        print("[INFO] Testing OKX API credentials...")
        try:
            balance = self.get_balance("USDT")
            print(f"[SUCCESS] API credentials are working. Available USDT balance: {balance}")
        except Exception as e:
            print(f"[FAILURE] API credentials test failed: {e}")

