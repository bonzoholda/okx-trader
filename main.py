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
from datetime import datetime, timezone
import traceback
from fastapi.responses import JSONResponse

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

@app.get("/api/position")
def get_position_data():
    try:
        chart = getattr(bot, "chart_position", None)
        if chart:
            return JSONResponse(content=chart)
        # Option 1: 200 with message
        return JSONResponse(content={"message": "No active position"}, status_code=200)
        # Option 2: 204 no content
        # return Response(status_code=204)
    except Exception as e:
        print("Error in /api/position:", str(e))
        traceback.print_exc()
        return JSONResponse(content={"error": "Internal Server Error"}, status_code=500)

@app.get("/position_tracker", response_class=HTMLResponse)
async def position_tracker(request: Request):
    return templates.TemplateResponse("position_tracker.html", {"request": request})


@app.get("/api/portfolio")
def get_portfolio_data():
    try:
        if getattr(bot, "live_portfolio_data", None):
            return JSONResponse(content=bot.live_portfolio_data)
        return JSONResponse(content={"message": "Portfolio data unavailable"}, status_code=204)
    except Exception as e:
        print("Error in /api/portfolio:", str(e))
        traceback.print_exc()
        return JSONResponse(content={"error": "Internal Server Error"}, status_code=500)

@app.get("/portfolio_chart", response_class=HTMLResponse)
async def portfolio_chart(request: Request):
    return templates.TemplateResponse("portfolio_chart.html", {"request": request})

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
            # Tracking portfolio
            current_value = bot.get_portfolio_value()[0]
            growth_percent = ((current_value - bot.initial_portfolio_value) / bot.initial_portfolio_value) * 100

            bot.live_portfolio_data = {
                "initial": round(bot.initial_portfolio_value, 4),
                "init_timestamp": bot.initial_portfolio_timestamp,
                "current": round(current_value, 4),
                "growth_percent": round(growth_percent, 2),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # ---Checking portfolio growth before trading session
            bot.check_portfolio_trailing()
            time.sleep(POLL_INTERVAL)
            bot.check_portfolio_shrink()
            time.sleep(POLL_INTERVAL)
            
            signal = data.get("signal")
            pair = data.get("pair")
            log_event(f"[DEBUG] Received signal: {signal}, pair: {pair}")

            if bot.active_position:

                log_event("[IDLE] Already in position. Skipping signal.")
                price = client.get_price()
                msg = bot.check_tp_sl(price)
                if msg:
                    log_event(msg)
                time.sleep(POLL_INTERVAL)
                continue

            # Normalize signal
            signal_map = {
                "long-divergence": "long",
                "short-divergence": "short"
            }
            signal = signal_map.get(signal, signal)

            if signal not in ["long", "short"]:
                log_event(f"[IDLE] Unknown signal received: {signal}")
                time.sleep(POLL_INTERVAL)
                continue

            if not pair or pair.upper() != SYMBOL.upper():
                log_event(f"[IDLE] Signal pair mismatch: {pair} != {SYMBOL}")
                time.sleep(POLL_INTERVAL)
                continue

            price = client.get_price()
            if not price:
                log_event("[ERROR] Failed to fetch price. Skipping trade.")
                time.sleep(POLL_INTERVAL)
                continue

            log_event(f"[TRADE] Executing {signal.upper()} for {SYMBOL.upper()} at price: {price}")
            msg = bot.open_position(signal, price)
            if msg:
                log_event(msg)
                 time.sleep(POLL_INTERVAL)

        except Exception as e:
            log_event(f"[ERROR] Main loop logic failed: {e}")

        time.sleep(POLL_INTERVAL)


def start_api():
    uvicorn.run(app, host="0.0.0.0", port=8080)

# Entry point
if __name__ == "__main__":
    # Start FastAPI in a separate thread
    threading.Thread(target=start_api, daemon=True).start()

    # Init tracking
    bot.initial_portfolio_value = bot.get_portfolio_value()[0]  # only `total`
    bot.initial_portfolio_timestamp = datetime.now(timezone.utc).isoformat()

    # Start the bot loop in main thread
    bot_loop()
