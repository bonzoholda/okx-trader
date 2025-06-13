import time
from client import OKXClient
from datetime import datetime, timezone

from config import (
    SIGNAL_SERVER_URL, SYMBOL, BASE_CURRENCY, QUOTE_CURRENCY,
    ORDER_PERCENT, DCA_PERCENT, TRAIL_TRIGGER, TRAIL_BUFFER,
    LONG_THRESHOLD, SHORT_THRESHOLD
)

from config import TP_DEFAULT, SL_DEFAULT

client = OKXClient()

class TradingBot:
    def __init__(self):
        self.active_position = None
        self.entry_price = None
        self.trailing_tp = None
        self.chart_position = None
        self.open_timestamp = None
        self.tp_target = None
        self.tp_count = 0
        self.dca_count = 0
        self.profit_capture = 0
        self.loss_limit = 0

        self.initial_portfolio_value = self.get_portfolio_value()[0]  # permanent for display
        self.init_tracking_point = self.initial_portfolio_value       # updated on each force sell
        self.tracking_trigger = self.init_tracking_point
        self.tracking_active = False
        self.shrinking_active = False

        self.tp_threshold = TP_DEFAULT
        self.sl_threshold = SL_DEFAULT

    def fetch_signal(self):
        try:
            res = client.session.get(SIGNAL_SERVER_URL)
            if res.status_code == 200:
                return res.json()  # Return full JSON dict, not just signal string
        except Exception as e:
            print(f"[ERROR] Failed to fetch signal: {e}")
        return None

    def get_portfolio_value(self):
        pi = client.get_balance(QUOTE_CURRENCY)
        usdt = client.get_balance(BASE_CURRENCY)
        price = client.get_price()
        return usdt + (pi * price), usdt, pi, price

    def calculate_amount(self, percent, price):
        portfolio_value, _, _, _ = self.get_portfolio_value()
        usdt_value = portfolio_value * percent
        return usdt_value / price

    def force_sell_all(self):
        _, _, pi_balance, _ = self.get_portfolio_value()
        if pi_balance > 0:
            result = client.place_order("short", pi_balance)
            print(f"[FORCE SELL] Sold {pi_balance} PI to lock portfolio growth.")
        else:
            print("[FORCE SELL] No PI to sell.")

    def check_portfolio_trailing(self):
        current_value, _, pi_balance, _ = self.get_portfolio_value()

        if not self.tracking_active and current_value > self.init_tracking_point * 1.005:
            self.tracking_active = True
            print("[TRAILING] Growth threshold reached. Tracking activated.")

        if self.tracking_active and current_value > self.init_tracking_point:
            self.init_tracking_point = current_value
            self.tracking_trigger = self.init_tracking_point * 0.999

        if self.tracking_active and current_value < self.tracking_trigger and pi_balance > 0:
            print("[TRAILING EXIT] Force sell triggered.")
            self.force_sell_all()
            self.profit_capture += 1
            self.init_tracking_point = self.get_portfolio_value()[0]
            self.tracking_trigger = self.init_tracking_point
            self.tracking_active = False
            self.reset_session()

    def check_portfolio_shrink(self):
        current_value, _, pi_balance, _ = self.get_portfolio_value()

        if not self.shrinking_active and current_value < self.init_tracking_point * 0.995:
            self.shrinking_active = True
            self.tracking_trigger = self.init_tracking_point * 0.995
            print("[SHRINK] Shrink threshold reached. Emergency exit activated.")

        if self.shrinking_active and current_value <= self.tracking_trigger and pi_balance > 0:
            print("[SHRINK EXIT] Force sell triggered.")
            self.force_sell_all()
            self.loss_limit += 1
            self.init_tracking_point = self.get_portfolio_value()[0]
            self.tracking_trigger = self.init_tracking_point
            self.shrinking_active = False
            self.reset_session()    

    def open_position(self, signal, price):
        portfolio_value, usdt, pi, _ = self.get_portfolio_value()

        signal_data = self.fetch_signal()
        
        if signal_data:
            signal_type = signal_data.get("signal")
            signal_price = signal_data.get("price")
            tp = signal_data.get("tp")
            sl = signal_data.get("sl")
        
            print(f"Signal: {signal_type}, Entry: {signal_price}, TP: {tp}, SL: {sl}")
            signal = signal_type
            self.tp_threshold = tp
            self.sl_threshold = sl
        
        if signal == "long":
            TP_THRESHOLD = self.tp_threshold
            
            if usdt < LONG_THRESHOLD * portfolio_value:
                print("Skipped trade, not enough USDT to buy")
                return
            amount = self.calculate_amount(ORDER_PERCENT, price)
            result = client.place_order("long", amount)
            if result.get("code") != "0":
                print(f"[ERROR] LONG order failed: {result.get('msg', 'Unknown error')}")
                return
            self.active_position = "long"
            self.entry_price = price
            self.trailing_tp = price * (1 + TP_THRESHOLD)
            self.tp_target = self.trailing_tp
            self.open_timestamp = datetime.now(timezone.utc).isoformat()
            print(f"[LONG] Opened at {price}")

        elif signal == "short":
            TP_THRESHOLD = self.tp_threshold
            
            if pi * price < SHORT_THRESHOLD * portfolio_value:
                print("Skipped trade, not enough PI to sell")
                return
            quote_amount = self.calculate_amount(ORDER_PERCENT, price)
            amount = quote_amount / price  # convert to base amount
            result = client.place_order("short", amount)
            if result.get("code") != "0":
                print(f"[ERROR] SHORT order failed: {result.get('msg', 'Unknown error')}")
                return
            self.active_position = "short"
            self.entry_price = price
            self.trailing_tp = price * (1 - TP_THRESHOLD)
            self.tp_target = self.trailing_tp
            self.open_timestamp = datetime.now(timezone.utc).isoformat()
            print(f"[SHORT] Opened at {price}")

    def check_tp_sl(self, price):
        TP_THRESHOLD = self.tp_threshold
        SL_THRESHOLD = self.sl_threshold * 3
        
        if not self.active_position or not self.entry_price:
            return

        change = (price - self.entry_price) / self.entry_price
        if self.active_position == "short":
            change = -change

        live_pnl = (price - self.entry_price) / self.entry_price
        if self.active_position == "short":
            live_pnl = -live_pnl

        sl_target = self.entry_price * (1 + SL_THRESHOLD) if self.active_position == "long" else self.entry_price * (1 - SL_THRESHOLD)

        self.chart_position = {
            "side": self.active_position,
            "entry": self.entry_price,
            "tp": self.trailing_tp,
            "timestamp": self.open_timestamp,
            "current_price": price,
            "live_pnl_percent": round(live_pnl * 100, 2),
            "tp_count": self.tp_count,
            "dca_count": self.dca_count,
            "sl": sl_target,
            "profit_capture": self.profit_capture,
            "loss_limit": self.loss_limit
        }

        locked_tp = self.trailing_tp

        if change >= (TP_THRESHOLD + TRAIL_TRIGGER):
            if self.active_position == "long":
                self.trailing_tp = max(self.trailing_tp, price - TRAIL_TRIGGER * price)
            else:
                self.trailing_tp = min(self.trailing_tp, price + TRAIL_TRIGGER * price)
            print(f"[TRAILING] Updated TP: {self.trailing_tp}")

        elif change >= TP_THRESHOLD:
            if self.active_position == "long":
                self.trailing_tp = price * (1 - TRAIL_BUFFER)
            else:
                self.trailing_tp = price * (1 + TRAIL_BUFFER)
            print(f"[TP HIT] Activated static TP: {self.trailing_tp}")

        elif change <= SL_THRESHOLD:
            self.dca_count += 1
            self.dca_and_close()
            return

        else:
            print(f"[MONITORING] Position: {self.active_position}, Entry: {self.entry_price}, TP: {self.trailing_tp} | Chart: {self.chart_position}")
            return

        if self.active_position == "long" and self.trailing_tp > locked_tp:
            locked_tp = self.trailing_tp
        elif self.active_position == "short" and self.trailing_tp < locked_tp:
            locked_tp = self.trailing_tp

        updated_price = client.get_price()
        if self.active_position == "long" and updated_price <= locked_tp and updated_price > self.tp_target:
            print(f"[EXIT] Long hit locked TP {locked_tp}, current price {updated_price}")
            self.tp_count += 1
            self.close_position("long")
        elif self.active_position == "short" and updated_price >= locked_tp and updated_price < self.tp_target:
            print(f"[EXIT] Short hit locked TP {locked_tp}, current price {updated_price}")
            self.tp_count += 1
            self.close_position("short")

    def close_position(self, side):
        price = client.get_price()

        if side == "short":
            amount = self.calculate_amount(ORDER_PERCENT, price)  # quote-based
        else:
            quote_amount = self.calculate_amount(ORDER_PERCENT, price)
            amount = quote_amount / price  # convert to base amount   
            
        success = client.place_order("short" if side == "long" else "long", amount)
        if not success:
            print("[ERROR] Failed to close position — order rejected.")
        self.active_position = None
        self.entry_price = None
        self.trailing_tp = None
        self.open_timestamp = None
        self.chart_position = None
        self.tp_target = None

        self.tp_threshold = TP_DEFAULT
        self.sl_threshold = SL_DEFAULT
        
        print(f"[CLOSED] {side.upper()} position closed.")

        self.chart_position = {
            "side": "",
            "entry": 0,
            "tp": 0,
            "timestamp": 0,
            "current_price": 0,
            "live_pnl_percent": 0,
            "tp_count": self.tp_count,
            "dca_count": self.dca_count,
            "sl": 0,
            "profit_capture": self.profit_capture,
            "loss_limit": self.loss_limit            
        }

    def dca_and_close(self):
        _, _, _, price = self.get_portfolio_value()
        
        dca_amount = self.calculate_amount(DCA_PERCENT, price)
        side = "long" if self.active_position == "long" else "short"

        if side == "long":
            dca_amount = self.calculate_amount(DCA_PERCENT, price)  # quote-based
        else:
            quote_amount = self.calculate_amount(DCA_PERCENT, price)
            dca_amount = quote_amount / price  # convert to base amount
        
        client.place_order(side, dca_amount)
        self.active_position = None
        self.entry_price = None
        self.trailing_tp = None
        self.chart_position = None
        self.open_timestamp = None
        self.tp_target = None

        self.tp_threshold = TP_DEFAULT
        self.sl_threshold = SL_DEFAULT
        
        print(f"[DCA] Added more to {side} before closing")

        self.chart_position = {
            "side": "",
            "entry": 0,
            "tp": 0,
            "timestamp": 0,
            "current_price": 0,
            "live_pnl_percent": 0,
            "tp_count": self.tp_count,
            "dca_count": self.dca_count,
            "sl": 0,
            "profit_capture": self.profit_capture,
            "loss_limit": self.loss_limit            
        }

    def reset_session(self):
        
        self.active_position = None
        self.entry_price = None
        self.trailing_tp = None
        self.open_timestamp = None
        self.chart_position = None
        self.tp_target = None

        self.tp_threshold = TP_DEFAULT
        self.sl_threshold = SL_DEFAULT
        
        print(f"[RESET] Trading session reset after force sell")

        self.chart_position = {
            "side": "",
            "entry": 0,
            "tp": 0,
            "timestamp": 0,
            "current_price": 0,
            "live_pnl_percent": 0,
            "tp_count": self.tp_count,
            "dca_count": self.dca_count,
            "sl": 0,
            "profit_capture": self.profit_capture,
            "loss_limit": self.loss_limit            
        }
