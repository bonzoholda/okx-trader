import time
import threading
from trading import TradingBot
from client import OKXClient
import requests
from config import SIGNAL_SERVER_URL, SYMBOL

import uvicorn
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime


bot = TradingBot()
client = OKXClient()
client.test_connection()

POLL_INTERVAL = 10  # seconds
log_queue = asyncio.Queue()

app = FastAPI()

# Allow CORS for local testing or frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup static and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/stats")
def get_stats():
    total, usdt, pi, price = bot.get_portfolio_value()
    return {
        "total": round(total, 4),
        "usdt": round(usdt, 4),
        "pi": round(pi, 4),
        "price": round(price, 4)
    }

@app.get("/logs")
async def stream_logs():
    async def event_generator():
        while True:
            message = await log_queue.get()
            yield f"data: {message}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

def log_event(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    asyncio.run(log_queue.put(full_msg))


def bot_loop():
    print("🚀 OKX Trader bot started.")
    while True:
        try:
            response = requests.get(SIGNAL_SERVER_URL)
            data = response.json()
        except Exception as e:
            log_event(f"[ERROR] Failed to fetch or parse signal: {e}")
            time.sleep(POLL_INTERVAL)
            continue
        
        try:
            signal = data.get("signal")
            pair = data.get("pair")
            log_event(f"[DEBUG] Received signal: {signal}, pair: {pair}")
            
            valid_signals = ["long", "short"]
            if signal not in valid_signals:
                #log_event(f"[IDLE] Unknown signal received: {signal}")
                #bypass signal long to trigger purchase
                signal = "long"
                time.sleep(POLL_INTERVAL)
                continue

            
            if not pair or pair.upper() != SYMBOL.upper():
                log_event(f"[IDLE] Signal pair mismatch: {pair} != {SYMBOL}")
                time.sleep(POLL_INTERVAL)
                continue
        
            if not signal:
                log_event("[IDLE] No valid signal received.")
                time.sleep(POLL_INTERVAL)
                continue
               
            if bot.active_position:
                log_event("[IDLE] Already in position. Skipping signal.")
                time.sleep(POLL_INTERVAL)
                continue
        
            price = bot.get_portfolio_value()[-1]
            if not price:
                log_event("[ERROR] Failed to fetch price. Skipping trade.")
                time.sleep(POLL_INTERVAL)
                continue
        
            log_event(f"[TRADE] Executing {signal.upper()} for {SYMBOL.upper()} at price: {price}")
            bot.open_position(signal, price)
        
        except Exception as e:
            log_event(f"[ERROR] Main loop logic failed: {e}")

        
        time.sleep(POLL_INTERVAL)

def start_api():
    uvicorn.run(app, host="0.0.0.0", port=8080)

# Entry point
if __name__ == "__main__":
    # Start FastAPI in a separate thread
    threading.Thread(target=start_api, daemon=True).start()

    # Start the bot loop in main thread
    bot_loop()
