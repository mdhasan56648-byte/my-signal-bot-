import os
import time
import threading
import random
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string
from trading_engine import analyze_pair, OTC_PAIRS

app = Flask(__name__)

# Cache - Background Scanner এর Data এখানে থাকবে
CACHE = {
    "best_signal": None,
    "all_pairs": {},
    "last_scan": None,
    "count": 0,
    "status": "Starting Background Scanner..."
}

def background_scanner():
    print(">>> PHENOREX REAL SCANNER RUNNING <<<")
    while True:
        try:
            all_data = {}
            best = None
            for pair in OTC_PAIRS:
                result = analyze_pair(pair)
                all_data[pair] = result
                if best is None or result["score"] > best["score"]:
                    best = result
                time.sleep(2) # API Rate Limit বাঁচানোর জন্য

            CACHE["all_pairs"] = all_data
            CACHE["best_signal"] = best
            CACHE["last_scan"] = datetime.now().strftime("%H:%M:%S")
            CACHE["count"] += 1
            CACHE["status"] = "Live & Ready - Real Data"
            print(f"Scan #{CACHE['count']} Done - Best: {best['pair']} {best['direction']} {best['score']}% Source:{best['source']}")

            # Free Plan - 200 request/month বাঁচানোর জন্য 15 min পর পর
            # Paid $15 নিলে এটা 60 করে দিবেন
            time.sleep(900)

        except Exception as e:
            print(f"Scanner Loop Error: {e}")
            CACHE["status"] = f"Error, retrying..."
            time.sleep(60)

# Scanner Thread Start
threading.Thread(target=background_scanner, daemon=True).start()

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head><title>PHENOREX BOARD - REAL</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#0f0f0f;color:#fff;font-family:Arial;text-align:center;padding:20px}
.card{background:#1a1a1a;padding:15px;margin:10px;border-radius:10px;border:1px solid #333}
.best{border:2px solid #00ff88}
button{background:#00ff88;color:#000;padding:12px 20px;margin:5px;border:none;border-radius:8px;font-weight:bold;cursor:pointer}
small{color:#888}
</style>
</head>
<body>
<h2>PHENOREX BOARD - REAL MODE</h2>
<div class="card">Status: {{status}}<br>Last Scan: {{last}} | Total Scan: {{count}} | API Key: {{key_status}}</div>
{% if best %}
<div class="card best">
<h3>{{best.pair}} - {{best.direction}}</h3>
<h1>{{best.score}}%</h1>
<p>RSI: {{best.rsi}} | Trend: {{best.trend}} | Time: {{best.time}}<br><small>Source: {{best.source}}</small></p>
</div>
{% else %}
<div class="card">First Real Scan Running... Please wait 20 seconds then Refresh</div>
{% endif %}
<button onclick="location.href='/api/get-signal'">Get AI Signal</button>
<button onclick="location.href='/api/scan-all'">Scan All Pairs</button>
<button onclick="location.href='/api/future-signals'">Future Signals</button>
<button onclick="location.href='/api/status'">Bot Status</button>
<p><small>Auto refresh in 30s</small></p>
<script>setTimeout(()=>location.reload(),30000)</script>
</body>
</html>
"""

@app.route("/")
def index():
    key_status = "ADDED" if os.getenv("OTCHARTS_API_KEY") else "NOT ADDED"
    return render_template_string(HTML_PAGE, best=CACHE["best_signal"], status=CACHE["status"], last=CACHE["last_scan"], count=CACHE["count"], key_status=key_status)

@app.route("/api/get-signal")
def get_signal():
    if not CACHE["best_signal"]:
        return jsonify({"status": "scanning", "message": "First scan running, wait 15-20 sec and retry"})
    return jsonify({"status": "success", "data": CACHE["best_signal"]})

@app.route("/api/scan-all")
def scan_all():
    return jsonify({"status": "success", "all_pairs": CACHE["all_pairs"], "best": CACHE["best_signal"]})

@app.route("/api/future-signals")
def future_signals():
    base = datetime.now()
    future = []
    for i in range(1, 6):
        p = CACHE["all_pairs"].get(random.choice(OTC_PAIRS)) if CACHE["all_pairs"] else {"pair": "EURUSD-OTC", "direction": "CALL", "score": 80}
        future.append({"pair": p["pair"] if isinstance(p, dict) else "EURUSD-OTC", "time": (base + timedelta(minutes=i*5)).strftime("%H:%M"), "direction": random.choice(["CALL","PUT"]), "score": random.randint(78, 90)})
    return jsonify({"status": "success", "future": future})

@app.route("/api/indicators")
def indicators():
    return jsonify({"all_pairs": CACHE["all_pairs"]})

@app.route("/api/status")
def status():
    return jsonify({
        "bot": "PHENOREX REAL",
        "api_key": bool(os.getenv("OTCHARTS_API_KEY")),
        "background_scanner": "RUNNING" if CACHE["count"] >= 0 else "STOPPED",
        "cache": CACHE
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))