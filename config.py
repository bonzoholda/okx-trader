import os
from dotenv import load_dotenv

# Load .env file for secrets (you should create a .env file in project root)
load_dotenv()

# === OKX API Credentials ===
OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_SECRET_KEY = os.getenv("OKX_SECRET_KEY")
OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE")
OKX_BASE_URL = "https://www.okx.com"

# === Signal Server ===
SIGNAL_SERVER_URL = "https://okx-signal-server.up.railway.app/api/signal"

# === Trading Settings ===
SYMBOL = "PI-USDT"              # Market pair (spot)
BASE_CURRENCY = "USDT"
QUOTE_CURRENCY = "PI"

ORDER_PERCENT = 0.12         # 12% of portfolio for initial entry
DCA_PERCENT = 0.18           # 18% for DCA on SL trigger

LONG_THRESHOLD = 0.30           # USDT must be > 30% of portfolio to open long
SHORT_THRESHOLD = 0.30          # PI must be > 30% of portfolio to open short

TP_DEFAULT = 0.005          # 0.5% TP
SL_DEFAULT = -0.015           # -1.5% SL triggers DCA
TRAIL_TRIGGER = 0.002     # Trailing triggers 0.2% above TP
TRAILING_STEP_PCT = 0.002       # Update TP if price rises/falls further
TRAIL_BUFFER = 0.001  # 0.1%

# === Polling Interval ===
SIGNAL_CHECK_INTERVAL = 10      # Seconds between signal checks

# === Logging ===
LOG_LEVEL = "INFO"              # Could be "DEBUG", "INFO", "WARNING"
