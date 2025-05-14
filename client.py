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
        self.base_url = OKX_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": OKX_API_KEY,
            "OK-ACCESS-PASSPHRASE": OKX_PASSPHRASE,
        })

    def _signature(self, timestamp, method, request_path, body=""):
        message = f"{timestamp}{method}{request_path}{body}"
        mac = hmac.new(OKX_SECRET_KEY.encode(), message.encode(), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode()

    def _request(self, method, path, params=None, body=None):
        url = self.base_url + path
        timestamp = datetime.utcnow().isoformat("T", "milliseconds") + "Z"
        body_json = json.dumps(body) if body else ""
        sign = self._signature(timestamp, method, path, body_json)

        headers = {
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
        }

        self.session.headers.update(headers)

        try:
            if method == "GET":
                response = self.session.get(url, params=params)
            else:
                response = self.session.request(method, url, data=body_json)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[ERROR] API request failed: {e}")
            return None

    # === PUBLIC API ===
    def get_price(self):
        response = self._request("GET", f"/api/v5/market/ticker", params={"instId": SYMBOL})
        if response and response.get("data"):
            return float(response["data"][0]["last"])
        return None

    # === PRIVATE APIs ===

    def get_balance(self, currency):
        result = self._request("GET", "/api/v5/account/balance", params={"ccy": currency})
        if result and result.get("data"):
            for item in result["data"][0]["details"]:
                if item["ccy"] == currency:
                    return float(item["availBal"])
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
