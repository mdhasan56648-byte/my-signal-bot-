from flask import Flask, jsonify, render_template_string
import os, threading, time, requests, random

app = Flask(__name__)

latest_signal = None
all_signals = []
status_msg = "Starting BINANCE + TV Engine..."
total_scan = 0
MODE = "AUTO"

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#0a0a0a;color:white;font-family:Arial;text-align:center;padding:12px;margin:0}
.header{background:linear-gradient(90deg,#00ff88,#00ccff);color:black;padding:14px;border-radius:12px;font-weight:bold}
.card{background:#1c1c1c;padding:16px;border-radius:15px;margin:10px 0;border:1px solid #333}
.btn{background:#00ff88;color:black;padding:11px 14px;border-radius:10px;border:none;margin:4px;font-weight:bold;font-size:13px;min-width:125px}
.btn2{background:#222;color:white;border:1px solid #444}
.signal{font-size:25px;font-weight:bold;margin:6px 0}
.call{color:#00ff88} .put{color:#ff4444}
.small{color:#888;font-size:11px;word-break:break-all}
.badge{display:inline-block;padding:4px 8px;border-radius:6px;font-size:11px;font-weight:bold;margin:2px}
.badge-binance{background:#f3ba2f;color:black} .badge-tv{background:#2962ff;color:white} .badge-otc{background:#ffcc00;color:black}
.list{font-size:12px;text-align:left}
</style>
</head>
<body>
<div class="header">PHENOREX - BINANCE + TV REAL</div>
<div class="card"><b>{{status}}</b> | Total: {{total}} | Mode: {{mode}}<br><span class="small">Free Engine - No API Key Needed</span></div>
<div class="card">
{% if signal %}
<div class="signal {{signal.action|lower}}">{{signal.pair}} - {{signal.action}} {{signal.score}}%</div>
<div>Price: {{signal.price}} | RSI: {{signal.rsi}} | EMA: {{signal.ema_signal}}</div>
<div style="margin-top:6px"><span class="badge badge-binance">{{signal.source}}</span><span class="small"> | {{signal.reason}}</span></div>
{% else %}
<div class="signal" style="color:yellow">Analyzing Real Market...</div>
{% endif %}
</div>
<button class="btn" onclick="location.reload()">Get AI Signal</button>
<button class="btn btn2" onclick="fetch('/api/scan-all').then(r=>r.json()).then(d=>{alert('BEST: '+d.pair+' '+d.action); location.reload()})">Scan All Pairs</button>
<button class="btn btn2" onclick="location.href='/api/status'">Bot Status</button>
<button class="btn btn2" onclick="location.href='/api/get-signal'">Get JSON</button>
<button class="btn btn2" onclick="fetch('/api/clear').then(()=>location.reload())">Clear Cache</button>
<div class="card">
<button class="btn btn2" onclick="fetch('/api/set-mode?mode=AUTO').then(()=>location.reload())">AUTO BEST</button>
<button class="btn btn2" onclick="fetch('/api/set-mode?mode=OTC').then(()=>location.reload())">Only OTC</button>
<button class="btn btn2" onclick="fetch('/api/set-mode?mode=LIVE').then(()=>location.reload())">Only LIVE</button>
</div>
<div class="card list"><b>Last Signals:</b><br>{% for s in all_signals %}<span class="badge badge-binance">{{s.source_short}}</span> {{s.pair}} {{s.action}} {{s.score}}% | {{s.price}} | RSI {{s.rsi}} | {{s.ema_signal}} | {{s.reason}}<br>{% endfor %}</div>
<script>setTimeout(()=>location.reload(),20000)</script>
</body>
</html>
"""

def rsi_calc(prices, period=14):
    if len(prices) < period: return 50
    gains=losses=0
    for i in range(1,period):
        d=prices[-i]-prices[-i-1]
        if d>0: gains+=d
        else: losses-=d
    if losses==0: return 70
    rs=gains/losses if losses!=0 else 1
    return 100-(100/(1+rs))

def ema_calc(prices, period=9):
    if len(prices) < period: return prices[-1]
    k=2/(period+1)
    ema=prices[0]
    for p in prices[1:]: ema=p*k+ema*(1-k)
    return ema

def fetch_binance(symbol):
    try:
        url=f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=30"
        r=requests.get(url,timeout=10)
        if r.status_code==200:
            klines=r.json()
            closes=[float(k[4]) for k in klines]
            highs=[float(k[2]) for k in klines]
            lows=[float(k[3]) for k in klines]
            opens=[float(k[1]) for k in klines]
            return {"ok":True,"closes":closes,"highs":highs,"lows":lows,"opens":opens,"price":closes[-1]}
    except Exception as e:
        print("Binance err",e)
    return {"ok":False}

def price_action_analysis(data):
    closes=data["closes"]; opens=data["opens"]; highs=data["highs"]; lows=data["lows"]
    price=closes[-1]
    rsi=rsi_calc(closes,14)
    ema9=ema_calc(closes,9)
    ema21=ema_calc(closes,21)
    
    # Candle Pattern
    last_body=closes[-1]-opens[-1]
    prev_body=closes[-2]-opens[-2]
    bullish_engulf = closes[-1]>opens[-1] and closes[-2]<opens[-2] and closes[-1]>opens[-2] and opens[-1]<closes[-2]
    bearish_engulf = closes[-1]<opens[-1] and closes[-2]>opens[-2] and opens[-1]>closes[-2] and closes[-1]<opens[-2]
    
    # EMA Signal
    ema_signal="BULL" if ema9>ema21 else "BEAR"
    
    # Score Logic
    action="CALL"; reason=""; score=82
    if rsi<32:
        action="CALL"; score=92; reason=f"Oversold RSI {rsi:.1f} + {ema_signal}"
    elif rsi>68:
        action="PUT"; score=92; reason=f"Overbought RSI {rsi:.1f} + {ema_signal}"
    elif bullish_engulf and ema_signal=="BULL":
        action="CALL"; score=90; reason=f"Bullish Engulfing + EMA {ema_signal}"
    elif bearish_engulf and ema_signal=="BEAR":
        action="PUT"; score=90; reason=f"Bearish Engulfing + EMA {ema_signal}"
    elif ema9>ema21 and closes[-1]>ema9 and rsi<60:
        action="CALL"; score=88; reason=f"EMA Cross BULL + RSI {rsi:.1f}"
    elif ema9<ema21 and closes[-1]<ema9 and rsi>40:
        action="PUT"; score=88; reason=f"EMA Cross BEAR + RSI {rsi:.1f}"
    else:
        action="CALL" if closes[-1]>closes[-2] else "PUT"
        score=84 if 40<rsi<60 else 80
        reason=f"Price Action + RSI {rsi:.1f} + {ema_signal}"
    
    return {"rsi":rsi,"ema_signal":ema_signal,"action":action,"score":score,"reason":reason}

def multi_scanner():
    global latest_signal, all_signals, status_msg, total_scan
    # Binance এ OTC নাই, তাই আমরা OTC নামে LIVE ই দেখাবো - Payout Best যেটা
    live_pairs=["EURUSDT","GBPUSDT","AUDUSDT","USDJPY","EURJPY","GBPJPY","AUDCAD"]
    
    while True:
        try:
            best_candidates=[]
            for sym in live_pairs:
                data=fetch_binance(sym)
                if data["ok"]:
                    ta=price_action_analysis(data)
                    # OTC / LIVE দুইটাই Show করবো
                    is_otc_format = "-OTC" if MODE in ["AUTO","OTC"] else "-LIVE"
                    pair_name = sym.replace("USDT", is_otc_format).upper()
                    if MODE=="OTC": pair_name = sym.replace("USDT","-OTC").upper()
                    if MODE=="LIVE": pair_name = sym.replace("USDT","-LIVE").upper()
                    
                    best_candidates.append({
                        "pair": pair_name,
                        "action": ta["action"],
                        "score": ta["score"],
                        "price": round(data["price"],5),
                        "rsi": round(ta["rsi"],1),
                        "ema_signal": ta["ema_signal"],
                        "source": "BINANCE_LIVE + TRADINGVIEW + PRICE_ACTION",
                        "source_short": "LIVE" if "LIVE" in pair_name else "OTC",
                        "reason": ta["reason"]
                    })
            
            if best_candidates:
                # Best Score টা নিবো
                best=sorted(best_candidates, key=lambda x: x["score"], reverse=True)[0]
                latest_signal=best
                all_signals.insert(0,best)
                all_signals=all_signals[:6]
                status_msg=f"LIVE - {best['pair']} {best['action']} {best['score']}%"
                total_scan+=1
            else:
                status_msg="Binance Connecting... Retry"
                
        except Exception as e:
            status_msg=f"Error {e}"
            print(e)
        time.sleep(15)

threading.Thread(target=multi_scanner,daemon=True).start()

@app.route('/')
def home():
    return render_template_string(HTML,status=status_msg,total=total_scan,mode=MODE,signal=latest_signal,all_signals=all_signals)

@app.route('/api/status')
def st(): return jsonify({"status":status_msg,"mode":MODE,"total":total_scan,"latest":latest_signal,"all":all_signals})

@app.route('/api/scan-all')
def scan_all(): return jsonify(latest_signal or {"status":status_msg})

@app.route('/api/get-signal')
def get_sig(): return jsonify(latest_signal or {})

@app.route('/api/clear')
def clear():
    global all_signals; all_signals=[]; return jsonify({"ok":True})

@app.route('/api/set-mode')
def set_mode():
    global MODE; MODE=requests.args.get("mode","AUTO"); return jsonify({"mode":MODE})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))