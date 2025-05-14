import time
from trading import TradingBot
from client import OKXClient
import requests
from config import SIGNAL_SERVER_URL, SYMBOL

bot = TradingBot()
client = OKXClient()

POLL_INTERVAL = 10  # seconds

def main():
    print("🚀 OKX Trader bot started.")
    while True:
        try:
            response = requests.get(SIGNAL_SERVER_URL)
            data = response.json()
        except Exception as e:
            print(f"[ERROR] Failed to fetch or parse signal: {e}")
            return  # exit this loop iteration safely
        
        try:
            signal = data.get("signal")
            pair = data.get("pair")
            print(f"[DEBUG] Received signal: {signal}, pair: {pair}")
        
            if pair != SYMBOL:
                print(f"[IDLE] Signal pair mismatch: {pair} != {SYMBOL}")
                return
        
            if not signal or bot.active_position:
                print("[IDLE] No signal or already in position.")
                return
        
            bot.execute_trade(signal)
        
        except Exception as e:
            print(f"[ERROR] Main loop logic failed: {e}")


        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
