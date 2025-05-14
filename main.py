import time
from trading import TradingBot
from client import OKXClient

bot = TradingBot()
client = OKXClient()

POLL_INTERVAL = 10  # seconds

def main():
    print("🚀 OKX Trader bot started.")
    while True:
        try:
            signal = bot.fetch_signal()
            print(f"Fetched signal: {data}")
            print(f"Bot symbol: {SYMBOL}, Signal pair: {pair}")
            price = client.get_price()

            if not bot.active_position and signal in ["long", "short"]:
                bot.open_position(signal, price)
            elif bot.active_position:
                bot.check_tp_sl(price)
            else:
                print(f"Position active: {bot.position_active}, Signal: {signal}")
                print("[IDLE] No signal or already in position.")

        except Exception as e:
            print(f"[ERROR] Main loop failed: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
