import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Small web server so Render port check passes
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is online and scanning!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# Run web server in a background thread
threading.Thread(target=run_server, daemon=True).start()

import yfinance as yf
import pandas as pd
import requests
import time

BOT_TOKEN = "8367707879:AAFG1UDCboyk5zSjPxpVRpElhIT9HaVzFos"
CHAT_ID = "7167357252"

# Assets to scan
WATCHLIST = {
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "AUDUSD=X": "AUD/USD",
    "USDCAD=X": "USD/CAD",
    "GC=F":     "Gold (XAU/USD)"
}

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

# Startup alert
send_telegram("🌍 *24/7 CLOUD SCANNER ONLINE!*\n\nScanning EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, and Gold continuously from Render.")

last_signals = {ticker: "NEUTRAL" for ticker in WATCHLIST}

while True:
    print("\n--- Starting Full Market Scan ---")
    
    for ticker, name in WATCHLIST.items():
        try:
            df = yf.download(tickers=ticker, period="5d", interval="15m", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if df.empty or len(df) < 200:
                continue

            df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
            df['EMA_50']  = df['Close'].ewm(span=50, adjust=False).mean()
            df['EMA_20']  = df['Close'].ewm(span=20, adjust=False).mean()

            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))

            latest = df.iloc[-1]
            price = round(float(latest['Close']), 4 if "JPY" in ticker or "GC=F" in ticker else 5)
            ema200 = round(float(latest['EMA_200']), 5)
            ema50 = round(float(latest['EMA_50']), 5)
            ema20 = round(float(latest['EMA_20']), 5)
            rsi = round(float(latest['RSI']), 2)

            current_signal = "NEUTRAL"
            if price > ema200 and ema20 > ema50 and 50 <= rsi <= 70:
                current_signal = "BUY"
            elif price < ema200 and ema20 < ema50 and 30 <= rsi <= 50:
                current_signal = "SELL"

            pip_offset = 0.50 if "GC=F" in ticker else (0.15 if "JPY" in ticker else 0.0015)

            if current_signal != "NEUTRAL" and current_signal != last_signals[ticker]:
                last_signals[ticker] = current_signal
                
                if current_signal == "BUY":
                    sl = round(price - pip_offset, 4 if "GC=F" in ticker else 5)
                    tp = round(price + (pip_offset * 2), 4 if "GC=F" in ticker else 5)
                    msg = f"🟢 *HIGH PROBABILITY BUY SIGNAL*\n\n• Asset: *{name}*\n• Entry Price: `{price}`\n• Stop Loss: `{sl}`\n• Take Profit: `{tp}`\n• RSI: `{rsi}`"
                else:
                    sl = round(price + pip_offset, 4 if "GC=F" in ticker else 5)
                    tp = round(price - (pip_offset * 2), 4 if "GC=F" in ticker else 5)
                    msg = f"🔴 *HIGH PROBABILITY SELL SIGNAL*\n\n• Asset: *{name}*\n• Entry Price: `{price}`\n• Stop Loss: `{sl}`\n• Take Profit: `{tp}`\n• RSI: `{rsi}`"

                send_telegram(msg)
                print(f"🚨 SIGNAL FIRED: {name} -> {current_signal} at {price}")
            else:
                print(f"  • {name}: {current_signal} | Price: {price} | RSI: {rsi}")

        except Exception as e:
            print(f"  • Error scanning {name}: {e}")

    time.sleep(900)
          
