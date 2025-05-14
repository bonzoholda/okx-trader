import time
from client import OKXClient
from config import (
    SIGNAL_API_URL, SYMBOL, BASE_CURRENCY, QUOTE_CURRENCY,
    ORDER_PERCENT, DCA_PERCENT, TP_THRESHOLD, SL_THRESHOLD, TRAIL_TRIGGER
)

client = OKXClient()


class TradingBot:
    def __init__(self):
        self.active_position = None  # "long" or "short"
        self.entry_price = None
        self.trailing_tp = None

    def fetch_signal(self):
        try:
            res = client.session.get(SIGNAL_API_URL)
            if res.status_code == 200:
                return res.json().get("signal")
        except Exception as e:
            print(f"[ERROR] Failed to fetch signal: {e}")
        return None

    def get_portfolio_value(self):
        usdt = client.get_balance(QUOTE_CURRENCY)
        pi = client.get_balance(BASE_CURRENCY)
        price = client.get_price()
        return usdt + (pi * price), usdt, pi, price

    def calculate_amount(self, percent, price):
        portfolio_value, _, _, _ = self.get_portfolio_value()
        usdt_value = portfolio_value * percent
        return usdt_value / price  # amount in BASE_CURRENCY

    def open_position(self, signal, price):
        portfolio_value, usdt, pi, _ = self.get_portfolio_value()

        if signal == "long" and usdt >= 0.3 * portfolio_value:
            amount = self.calculate_amount(ORDER_PERCENT, price)
            client.place_order("long", amount)
            self.active_position = "long"
            self.entry_price = price
            self.trailing_tp = price * (1 + TP_THRESHOLD)
            print(f"[LONG] Opened at {price}")

        elif signal == "short" and pi * price >= 0.3 * portfolio_value:
            amount = self.calculate_amount(ORDER_PERCENT, price)
            client.place_order("short", amount)
            self.active_position = "short"
            self.entry_price = price
            self.trailing_tp = price * (1 - TP_THRESHOLD)
            print(f"[SHORT] Opened at {price}")

    def check_tp_sl(self, price):
        if not self.active_position or not self.entry_price:
            return

        change = (price - self.entry_price) / self.entry_price
        if self.active_position == "short":
            change = -change

        # --- Trailing TP ---
        if change >= TP_THRESHOLD + TRAIL_TRIGGER:
            if self.active_position == "long":
                self.trailing_tp = max(self.trailing_tp, price - TRAIL_TRIGGER * price)
            else:
                self.trailing_tp = min(self.trailing_tp, price + TRAIL_TRIGGER * price)
            print(f"[TRAILING] Updated TP: {self.trailing_tp:.4f}")

        # --- Close at trailing TP ---
        if self.active_position == "long" and price < self.trailing_tp:
            self.close_position("long")
        elif self.active_position == "short" and price > self.trailing_tp:
            self.close_position("short")

        # --- DCA on SL ---
        if change <= SL_THRESHOLD:
            self.dca_and_close()

    def close_position(self, side):
        amount = client.get_position_size(BASE_CURRENCY if side == "long" else QUOTE_CURRENCY)
        client.place_order("short" if side == "long" else "long", amount)
        print(f"[CLOSE] {side.upper()} closed")
        self.active_position = None
        self.entry_price = None
        self.trailing_tp = None

    def dca_and_close(self):
        _, _, _, price = self.get_portfolio_value()
        dca_amount = self.calculate_amount(DCA_PERCENT, price)
        side = "long" if self.active_position == "long" else "short"
        client.place_order(side, dca_amount)
        print(f"[DCA] Added more to {side} before closing")
        self.close_position(side)
