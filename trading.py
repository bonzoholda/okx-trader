import time
from client import OKXClient
from config import (
    SIGNAL_SERVER_URL, SYMBOL, BASE_CURRENCY, QUOTE_CURRENCY,
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
            res = client.session.get(SIGNAL_SERVER_URL)
            if res.status_code == 200:
                return res.json().get("signal")
        except Exception as e:
            print(f"[ERROR] Failed to fetch signal: {e}")
        return None

    def get_portfolio_value(self):
        pi = client.get_balance(QUOTE_CURRENCY)       # e.g. PI
        usdt = client.get_balance(BASE_CURRENCY)    # e.g. USDT
        price = client.get_price()
        return usdt + (pi * price), usdt, pi, price

    def calculate_amount(self, percent, price):
        portfolio_value, _, _, _ = self.get_portfolio_value()
        usdt_value = portfolio_value * percent
        return usdt_value / price  # amount in BASE_CURRENCY

    def open_position(self, signal, price):
        portfolio_value, usdt, pi, _ = self.get_portfolio_value()
    
        # --- LONG ---
        if signal == "long":
            if usdt < 0.3 * portfolio_value:
                msg = "Skipped trade, not enough USDT to buy"
                print(msg)
                return msg
            
            amount = self.calculate_amount(ORDER_PERCENT, price)
            result = client.place_order("long", amount)
    
            if result.get("code") != "0":
                msg = f"[ERROR] LONG order failed: {result.get('msg', 'Unknown error')}"
                print(msg)
                return msg
    
            self.active_position = "long"
            self.entry_price = price
            self.trailing_tp = price * (1 + TP_THRESHOLD)
            msg = f"[LONG] Opened at {price}"
            print(msg)
            return msg
    
        # --- SHORT ---
        elif signal == "short":
            if pi * price < 0.3 * portfolio_value:
                msg = "Skipped trade, not enough PI to sell"
                print(msg)
                return msg
    
            amount = self.calculate_amount(ORDER_PERCENT, price)
            result = client.place_order("short", amount)
    
            if result.get("code") != "0":
                msg = f"[ERROR] SHORT order failed: {result.get('msg', 'Unknown error')}"
                print(msg)
                return msg
    
            self.active_position = "short"
            self.entry_price = price
            self.trailing_tp = price * (1 - TP_THRESHOLD)
            msg = f"[SHORT] Opened at {price}"
            print(msg)
            return msg

    
    def check_tp_sl(self, price):
        if not self.active_position or not self.entry_price:
            return
    
        change = (price - self.entry_price) / self.entry_price
        if self.active_position == "short":
            change = -change
    
        # --- Trailing TP logic ---
        if change >= TP_THRESHOLD + TRAIL_TRIGGER:
            # Update trailing TP
            if self.active_position == "long":
                self.trailing_tp = max(self.trailing_tp or 0, price - TRAIL_TRIGGER * price)
            else:
                self.trailing_tp = min(self.trailing_tp or float('inf'), price + TRAIL_TRIGGER * price)
            msg = f"[TRAILING] Updated TP: {self.trailing_tp}"
            print(msg)
            return msg
    
        # --- TP reached but not enough for trailing ---
        elif change >= TP_THRESHOLD:
            # Set static trailing TP to TP level if not already set
            if not self.trailing_tp:
                self.trailing_tp = price  # lock it here
                msg = f"[TP HIT] Activated static TP: {self.trailing_tp}"
                print(msg)
                return msg
    
        # --- Close if price falls back below static/trailing TP ---
        if self.trailing_tp:
            if self.active_position == "long" and price < self.trailing_tp:
                self.close_position("long")
                return "[CLOSED] Long position closed at trailing TP"
            elif self.active_position == "short" and price > self.trailing_tp:
                self.close_position("short")
                return "[CLOSED] Short position closed at trailing TP"
    
        # --- DCA on SL ---
        if change <= SL_THRESHOLD:
            self.dca_and_close()
            return "[DCA] Stop loss triggered"
    
        # Monitoring only
        msg = f"[MONITORING] Position: {self.active_position}, Entry: {self.entry_price}, TP: {self.trailing_tp}"
        print(msg)
        return msg

            
        
    def close_position(self, side):
        amount = client.get_position_size(BASE_CURRENCY if side == "long" else QUOTE_CURRENCY)
        client.place_order("short" if side == "long" else "long", amount)
        msg=f"[CLOSE] {side.upper()} closed"
        print(msg)
        return msg
        self.active_position = None
        self.entry_price = None
        self.trailing_tp = None

    def dca_and_close(self):
        _, _, _, price = self.get_portfolio_value()
        dca_amount = self.calculate_amount(DCA_PERCENT, price)
        side = "long" if self.active_position == "long" else "short"
        client.place_order(side, dca_amount)
        msg=f"[DCA] Added more to {side} before closing"
        print(msg)
        return msg
        self.close_position(side)
