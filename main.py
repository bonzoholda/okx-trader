import time
from trading import TradingBot
from client import OKXClient
import requests
from config import SIGNAL_SERVER_URL, SYMBOL

bot = TradingBot()
client = OKXClient()
client.test_connection()

POLL_INTERVAL = 10  # seconds

def main():
    print("🚀 OKX Trader bot started.")
    while True:
        try:
            response = requests.get(SIGNAL_SERVER_URL)
            data = response.json()
        except Exception as e:
            print(f"[ERROR] Failed to fetch or parse signal: {e}")
            time.sleep(POLL_INTERVAL)
            continue  # retry next loop iteration

        try:
            signal = data.get("signal")
            pair = data.get("pair")
            print(f"[DEBUG] Received signal: {signal}, pair: {pair}")

            if pair != SYMBOL:
                print(f"[IDLE] Signal pair mismatch: {pair} != {SYMBOL}")
                time.sleep(POLL_INTERVAL)
                continue

            if not signal or bot.active_position:
                print("[IDLE] No signal or already in position.")
                # Log portfolio state even during idle
                portfolio_value, usdt, pi, price = bot.get_portfolio_value()
                print(f"[PORTFOLIO] Total: ${portfolio_value:.2f}, USDT: {usdt:.4f}, PI: {pi:.4f} @ Price: ${price:.4f}")
                time.sleep(POLL_INTERVAL)
                continue

            # Use latest price to open a position
            price = bot.get_portfolio_value()[-1]
            bot.open_position(signal, price)

            # Log portfolio after action
            portfolio_value, usdt, pi, price = bot.get_portfolio_value()
            print(f"[PORTFOLIO] Total: ${portfolio_value:.2f}, USDT: {usdt:.4f}, PI: {pi:.4f} @ Price: ${price:.4f}")

        except Exception as e:
            print(f"[ERROR] Main loop logic failed: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
