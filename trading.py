import time
from client import OKXClient
from datetime import datetime, timezone

from config import (
    SIGNAL_SERVER_URL, SYMBOL, BASE_CURRENCY, QUOTE_CURRENCY,
    ORDER_PERCENT, DCA_PERCENT, TP_THRESHOLD, SL_THRESHOLD, TRAIL_TRIGGER, TRAIL_BUFFER,
    LONG_THRESHOLD, SHORT_THRESHOLD
)

client = OKXClient()


class TradingBot:
    def __init__(self):
        self.active_position = None  # "long" or "short"
        self.entry_price = None
        self.trailing_tp = None
        self.chart_position = None
        self.open_timestamp = None

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
            if usdt < LONG_THRESHOLD * portfolio_value:
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

            self.open_timestamp = datetime.now(timezone.utc).isoformat()
            
            msg = f"[LONG] Opened at {price}"
            print(msg)
            return msg
    
        # --- SHORT ---
        elif signal == "short":
            if pi * price < SHORT_THRESHOLD * portfolio_value:
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

            self.open_timestamp = datetime.utcnow().isoformat()

            
            msg = f"[SHORT] Opened at {price}"
            print(msg)
            return msg

    
    def check_tp_sl(self, price):
        if not self.active_position or not self.entry_price:
            return
        
        change = (price - self.entry_price) / self.entry_price
        if self.active_position == "short":
            change = -change

        live_pnl = (price - self.entry_price) / self.entry_price
        if self.active_position == "short":
            live_pnl = -live_pnl
        
        self.chart_position = {
            "side": self.active_position,
            "entry": self.entry_price,
            "tp": self.trailing_tp,
            "timestamp": self.open_timestamp,
            "current_price": price,
            "live_pnl_percent": round(live_pnl * 100, 2)
        }

        
        # --- Trailing TP ---
        if change >= TP_THRESHOLD + TRAIL_TRIGGER:
            if self.active_position == "long":
                self.trailing_tp = max(self.trailing_tp, price - TRAIL_TRIGGER * price)
            else:
                self.trailing_tp = min(self.trailing_tp, price + TRAIL_TRIGGER * price)
            msg=f"[TRAILING] Updated TP: {self.trailing_tp}"
            print(msg)
            #return msg
        elif change < TP_THRESHOLD + TRAIL_TRIGGER:

            # --- TP reached but not enough for full trailing ---
            if change >= TP_THRESHOLD:
                if not self.trailing_tp:
                    if self.active_position == "long":
                        self.trailing_tp = price * (1 - TRAIL_BUFFER)
                    else:
                        self.trailing_tp = price * (1 + TRAIL_BUFFER)
                    msg = f"[TP HIT] Activated static TP: {self.trailing_tp}"
                    print(msg)
                    #return msg 
            else:
                msg=f"[MONITORING] Position: {self.active_position}, Entry: {self.entry_price}, TP: {self.trailing_tp} | Chart: {self.chart_position}"
                print(msg)
                return msg                
                

        # --- Close at trailing TP ---
        if self.active_position == "long" and price < self.trailing_tp:
            self.close_position("long")
        elif self.active_position == "short" and price > self.trailing_tp:
            self.close_position("short")

        # --- DCA on SL ---
        if change <= SL_THRESHOLD:
            self.dca_and_close()


            
        
    def close_position(self, side):
        price = client.get_price()
        # Try to place the reverse order
        if side == "long":
            success = self.open_position("short", price)
        else:
            success = self.open_position("long", price)
            
        if not success:
            print("[ERROR] Failed to close position — order rejected.")
            #return  # Don't reset state!
    
        # Only if success:
        self.active_position = None
        self.entry_price = None
        self.trailing_tp = None
        self.open_timestamp = None
        self.chart_position = None
        print(f"[CLOSED] {side.upper()} position closed.")


    def dca_and_close(self):
        _, _, _, price = self.get_portfolio_value()
        dca_amount = self.calculate_amount(DCA_PERCENT, price)
        side = "long" if self.active_position == "long" else "short"
        client.place_order(side, dca_amount)

        self.active_position = None
        self.entry_price = None
        self.trailing_tp = None
        self.chart_position = None
        self.open_timestamp = None
        msg=f"[DCA] Added more to {side} before closing"
        print(msg)
        return msg
