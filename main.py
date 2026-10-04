import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import yfinance as yf
import pandas as pd
import ta
import requests

# ==========================================
# 1. BACKGROUND WEB SERVER (FOR RENDER)
# ==========================================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is online and scanning!")

    def log_message(self, format, *args):
        return  # Suppress HTTP server noise in Render logs

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# ==========================================
# 2. TELEGRAM CONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def send_telegram_signal(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[Signal Alert]\n{message}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

# ==========================================
# 3. YAHOO FINANCE SAFE FETCH (RATE-LIMIT FIX)
# ==========================================
def safe_get_data(symbol, period="5d", interval="5m", max_retries=3):
    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if not df.empty and len(df) >= 200:
                return df
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e) or "crumb" in str(e).lower():
                wait_time = 5 * (attempt + 1)
                print(f"[!] Rate limit on {symbol}. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                time.sleep(2)
    return None

# ==========================================
# 4. ASSETS & STRATEGY ENGINE
# ==========================================
PAIRS = {
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "AUDUSD=X": "AUD/USD",
    "USDCAD=X": "USD/CAD",
    "GC=F": "XAU/USD (Gold)"
}

def analyze_and_signal(symbol, name):
    df = safe_get_data(symbol)
    if df is None or len(df) < 200:
        return

    # Calculate Indicators
    df['EMA_200'] = ta.trend.ema_indicator(df['Close'], window=200)
    df['EMA_50'] = ta.trend.ema_indicator(df['Close'], window=50)
    df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close = latest['Close']
    ema200 = latest['EMA_200']
    ema50 = latest['EMA_50']
    ema20 = latest['EMA_20']
    rsi = latest['RSI']

    prev_ema20 = prev['EMA_20']
    prev_ema50 = prev['EMA_50']

    # BUY Logic: 20 EMA crosses above 50 EMA, both above 200 EMA, RSI > 50
    bullish_cross = (prev_ema20 <= prev_ema50) and (ema20 > ema50)
    if bullish_cross and (ema20 > ema200) and (ema50 > ema200) and (rsi > 50):
        sl = round(close - (close * 0.0015), 5) if "GC=F" not in symbol else round(close - 3.0, 2)
        tp = round(close + (close * 0.0030), 5) if "GC=F" not in symbol else round(close + 6.0, 2)
        
        msg = (
            f"🚨 *BUY SIGNAL GENERATED*\n\n"
            f"📈 *Asset:* {name}\n"
            f"💵 *Entry:* {close:.5f}\n"
            f"🛑 *Stop Loss:* {sl}\n"
            f"🎯 *Take Profit:* {tp}\n"
            f"📊 *RSI:* {rsi:.2f}\n"
            f"⚡ *Lot Size:* 0.01\n\n"
            f"⏱ *Rule:* Execute within 2 minutes!"
        )
        send_telegram_signal(msg)

    # SELL Logic: 20 EMA crosses below 50 EMA, both below 200 EMA, RSI < 50
    bearish_cross = (prev_ema20 >= prev_ema50) and (ema20 < ema50)
    if bearish_cross and (ema20 < ema200) and (ema50 < ema200) and (rsi < 50):
        sl = round(close + (close * 0.0015), 5) if "GC=F" not in symbol else round(close + 3.0, 2)
        tp = round(close - (close * 0.0030), 5) if "GC=F" not in symbol else round(close - 6.0, 2)
        
        msg = (
            f"🚨 *SELL SIGNAL GENERATED*\n\n"
            f"📉 *Asset:* {name}\n"
            f"💵 *Entry:* {close:.5f}\n"
            f"🛑 *Stop Loss:* {sl}\n"
            f"🎯 *Take Profit:* {tp}\n"
            f"📊 *RSI:* {rsi:.2f}\n"
            f"⚡ *Lot Size:* 0.01\n\n"
            f"⏱ *Rule:* Execute within 2 minutes!"
        )
        send_telegram_signal(msg)

# ==========================================
# 5. MAIN SCANNING LOOP
# ==========================================
print("Forex Signal Bot started successfully!")
while True:
    print("Starting market scan...")
    for symbol, name in PAIRS.items():
        try:
            analyze_and_signal(symbol, name)
        except Exception as e:
            print(f"Error scanning {name}: {e}")
        time.sleep(2)  # 2-second delay between pairs prevents rate limits
    
    print("Scan complete. Waiting 15 minutes for next cycle...")
    time.sleep(900)
