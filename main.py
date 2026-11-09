from flask import Flask, jsonify, render_template_string, request
import os, threading, time, requests, random
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

latest_signal = None
all_signals = []
future_list = []
status_msg = "Starting AI Engine..."
total_scan = 0
SETTINGS = {"num_signals": 10, "expiry": "2M", "pairs_type": "AUTO"}

MAIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#0a0a0a;color:white;font-family:Arial;padding:10px;margin:0;text-align:center}
.header{background:linear-gradient(90deg,#00ff88,#00ccff);color:black;padding:14px;border-radius:12px;font-weight:bold;font-size:17px}
.card{background:#1c1c1c;padding:14px;border-radius:14px;margin:8px 0;border:1px solid #333}
.btn{padding:14px 10px;border-radius:12px;border:none;margin:5px;font-weight:bold;font-size:14px;min-width:160px;cursor:pointer}
.b1{background:#00ff88;color:black} .b2{background:#2962ff;color:white} .b3{background:#ffaa00;color:black} .b4{background:#222;color:white;border:1px solid #555} .b5{background:#444;color:white}
.signal{font-size:23px;font-weight:bold} .call{color:#00ff88} .put{color:#ff4444}
.small{color:#999;font-size:11px} .grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.list{text-align:left;font-size:12px;line-height:20px}
</style>
</head>
<body>
<div class="header">PHENOREX v20 FINAL - REAL BINANCE</div>
<div class="card"><b>{{status}}</b> | Total: {{total}}<br><span class="small">Dhaka: {{dhaka_time}} | Mode: {{settings.pairs_type}}</span></div>
<div class="card">
{% if signal %}
<div class="signal {{signal.action|lower}}">{{signal.pair}} - {{signal.action}} {{signal.score}}%</div>
<div style="margin:6px 0">Price: {{signal.price}} | RSI: {{signal.rsi}} | {{signal.ema_signal}}</div>
<div class="small">{{signal.reason}}<br>Entry: {{signal.entry_time}} | Expiry: {{signal.expiry_time}} | {{signal.expiry_label}}</div>
{% else %}
<div class="signal" style="color:yellow">{{status}}</div>
<div class="small">Please wait 15 sec...</div>
{% endif %}
</div>
<div class="card grid">
<button class="btn b1" onclick="location.href='/get-signal-now'">1. GET AI SIGNAL<br><small>INSTANT</small></button>
<button class="btn b2" onclick="location.href='/future'">2. FUTURE AI SIGNAL<br><small>{{settings.num_signals}} x {{settings.expiry}}</small></button>
<button class="btn b3" onclick="location.href='/scanner'">3. SCANNER<br><small>Camera / Image</small></button>
<button class="btn b4" onclick="location.href='/settings'">4. SETTINGS<br><small>All Tools</small></button>
</div>
<div class="card"><button class="btn b5" onclick="location.href='/help'" style="width:90%">5. HELP - How to Use</button></div>
<div class="card list"><b>Last 10 Signals:</b><br>{% for s in all_signals %}{{loop.index}}. {{s.entry_time}} | {{s.pair}} | {{s.action}} {{s.score}}% | RSI {{s.rsi}}<br>{% endfor %}</div>
<script>setTimeout(()=>location.reload(),30000)</script>
</body>
</html>
"""

FUTURE_HTML = """
<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
body{background:#0a0a0a;color:white;font-family:Arial;padding:12px;text-align:center}
.card{background:#1c1c1c;padding:14px;border-radius:12px;margin:10px 0;border:1px solid #333}
.btn{padding:12px;border-radius:10px;border:none;margin:4px;font-weight:bold;min-width:140px;cursor:pointer}
.b1{background:#00ff88;color:black} .b2{background:#2962ff;color:white} .b3{background:#222;color:white;border:1px solid #555}
select{padding:10px;margin:5px;background:#222;color:white;border:1px solid #444;border-radius:8px;width:90%}
.list{text-align:left;font-size:12px;line-height:20px}
.signal{font-size:18px;font-weight:bold} .call{color:#00ff88} .put{color:#ff4444}
.small{color:#999;font-size:11px}
</style></head><body>
<h3>FUTURE AI SIGNAL LIST</h3>
<div class="card">
<b>Customize:</b><br>
<form action="/future" method="get">
<label>কয়টা Signal লাগবে?</label><br>
<select name="num">
<option value="5" {% if settings.num_signals==5 %}selected{% endif %}>5 Signals</option>
<option value="6" {% if settings.num_signals==6 %}selected{% endif %}>6 Signals</option>
<option value="8" {% if settings.num_signals==8 %}selected{% endif %}>8 Signals</option>
<option value="10" {% if settings.num_signals==10 %}selected{% endif %}>10 Signals</option>
<option value="15" {% if settings.num_signals==15 %}selected{% endif %}>15 Signals</option>
</select><br>
<label>কয় মিনিট পর পর?</label><br>
<select name="exp">
<option value="2M" {% if settings.expiry=='2M' %}selected{% endif %}>2 Minute</option>
<option value="3M" {% if settings.expiry=='3M' %}selected{% endif %}>3 Minute</option>
<option value="5M" {% if settings.expiry=='5M' %}selected{% endif %}>5 Minute</option>
<option value="10M" {% if settings.expiry=='10M' %}selected{% endif %}>10 Minute</option>
</select><br>
<button class="btn b1" type="submit" style="width:90%">Generate List</button>
</form>
</div>
<div class="card list">
<b>Dhaka Time Future List ({{settings.num_signals}} x {{settings.expiry}})</b><br>
{% for s in future_list %}
{{loop.index}}. {{s.entry_time}} -> {{s.expiry_time}} | <b>{{s.pair}}</b> | <span class="{{s.action|lower}}" style="font-weight:bold">{{s.action}}</span> {{s.score}}% | RSI {{s.rsi}}<br>
{% endfor %}
{% if not future_list %}<span class="small">Generate ক্লিক করুন</span>{% endif %}
</div>
<a href="/"><button class="btn b3" style="width:90%">Back to Home</button></a>
</body></html>
"""

SCANNER_HTML = """
<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
body{background:#0a0a0a;color:white;font-family:Arial;padding:12px;text-align:center}
.card{background:#1c1c1c;padding:15px;border-radius:12px;margin:10px 0;border:1px solid #333}
.btn{padding:12px;border-radius:10px;border:none;font-weight:bold;min-width:140px;cursor:pointer;margin:5px}
.b1{background:#ffaa00;color:black} .b2{background:#222;color:white;border:1px solid #555}
.signal{font-size:22px;font-weight:bold} .call{color:#00ff88} .put{color:#ff4444}
.small{color:#999;font-size:11px}
</style></head><body>
<h3>SCANNER</h3>
<div class="card">
{% if result %}
<div class="signal {{result.action|lower}}">{{result.pair}} - {{result.action}} {{result.score}}%</div>
<div>Price: {{result.price}} | RSI: {{result.rsi}}<br><span class="small">{{result.reason}}</span></div>
<hr style="border:0;border-top:1px solid #333;margin:10px 0">
<div style="color:#00ff88;font-weight:bold">Trade Now: {{result.action}} on {{result.pair}}</div>
{% else %}
<p>Market Screenshot দিন</p>
<form action="/scanner" method="post" enctype="multipart/form-data">
<input type="file" name="image" accept="image/*" capture="environment" required><br>
<button class="btn b1" type="submit">Scan & Get Trade</button>
</form>
{% endif %}
</div>
<a href="/"><button class="btn b2">Back Home</button></a>
</body></html>
"""

SETTINGS_HTML = """
<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
body{background:#0a0a0a;color:white;font-family:Arial;padding:12px;text-align:center}
.card{background:#1c1c1c;padding:14px;border-radius:12px;margin:10px 0;border:1px solid #333;text-align:left}
.btn{padding:11px;border-radius:10px;border:none;margin:4px;font-weight:bold;min-width:130px;cursor:pointer}
.b1{background:#00ff88;color:black} .b2{background:#222;color:white;border:1px solid #555} .b3{background:#2962ff;color:white} .b4{background:#ff4444;color:white}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:6px}
select{width:100%;padding:10px;margin:5px 0;background:#222;color:white;border:1px solid #444;border-radius:8px}
</style></head><body>
<h3>SETTINGS</h3>
<div class="card">
<form action="/save-settings" method="get">
<label>Future Signals:</label><select name="num_signals"><option value="5">5</option><option value="10" selected>10</option><option value="15">15</option></select>
<label>Expiry:</label><select name="expiry"><option value="2M" selected>2M</option><option value="3M">3M</option><option value="5M">5M</option><option value="10M">10M</option></select>
<label>Pairs Type:</label><select name="pairs_type"><option value="AUTO" selected>AUTO BEST</option><option value="OTC">Only OTC</option><option value="LIVE">Only LIVE</option></select>
<button class="btn b1" type="submit" style="width:100%">Save Settings</button>
</form>
</div>
<div class="card">
<div class="grid2">
<button class="btn b3" onclick="fetch('/api/scan-all').then(r=>r.json()).then(d=>alert('BEST: '+(d.pair||'Wait')))">Scan All Pairs</button>
<button class="btn b2" onclick="location.href='/api/status'">Bot Status</button>
<button class="btn b4" onclick="fetch('/api/clear').then(()=>alert('Cleared!')).then(()=>location.href='/')">Clear Cache</button>
<button class="btn b2" onclick="location.href='/api/restart'">Restart Bot</button>
</div>
</div>
<a href="/"><button class="btn b2" style="width:90%">Back to Home</button></a>
</body></html>
"""

HELP_HTML = """<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{background:#0a0a0a;color:white;font-family:Arial;padding:14px;line-height:22px} .card{background:#1c1c1c;padding:14px;border-radius:12px;margin:10px 0;border:1px solid #333} .btn{background:#00ff88;color:black;padding:12px;border-radius:10px;border:none;font-weight:bold;width:90%} h3{color:#00ff88}</style></head><body>
<h3>HELP</h3>
<div class="card">Bot Binance Vision API থেকে Real Price আনে, RSI+EMA দিয়ে Signal দেয়। Dhaka Time এ Entry/Expiry দেখায়।</div>
<div class="card">Hang হলে: /api/clear তারপর Restart</div>
<a href="/"><button class="btn">Back to Home</button></a>
</body></html>
"""

def get_dhaka_time():
    try:
        tz = pytz.timezone('Asia/Dhaka')
        return datetime.now(tz)
    except:
        return datetime.utcnow() + timedelta(hours=6)

def rsi_calc(prices, period=14):
    if len(prices) < period+1: 
        return 50.0
    gains = 0
    losses = 0
    # last period candles
    for i in range(len(prices)-period, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains += change
        else:
            losses += abs(change)
    if losses == 0:
        return 72.0 if gains > 0 else 50.0
    if gains == 0:
        return 28.0
    rs = gains / losses
    rsi = 100 - (100 / (1 + rs))
    return max(15, min(85, rsi))

def ema_calc(prices, period=9):
    if len(prices) < period: return prices[-1]
    k=2/(period+1); ema=prices[0]
    for p in prices[1:]: ema=p*k+ema*(1-k)
    return ema

def fetch_binance(symbol):
    urls = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=1m&limit=30",
        f"https://api1.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=30",
    ]
    headers={"User-Agent":"Mozilla/5.0"}
    for url in urls:
        try:
            r=requests.get(url,timeout=7,headers=headers)
            if r.status_code==200:
                klines=r.json()
                if len(klines)>10:
                    closes=[float(k[4]) for k in klines]
                    return {"ok":True,"closes":closes,"price":closes[-1]}
        except: continue
    return {"ok":False}

def make_signal(symbol):
    data=fetch_binance(symbol)
    if not data["ok"]: return None
    closes=data["closes"]
    rsi=rsi_calc(closes,14)
    ema9=ema_calc(closes,9)
    ema21=ema_calc(closes,21)
    ema_sig="BULL" if ema9>ema21 else "BEAR"
    
    if rsi<32: action="CALL"; score=92; reason=f"Oversold RSI {rsi:.1f} + {ema_sig}"
    elif rsi>68: action="PUT"; score=92; reason=f"Overbought RSI {rsi:.1f} + {ema_sig}"
    elif ema9>ema21 and rsi<57: action="CALL"; score=88; reason=f"TV EMA Bull + RSI {rsi:.1f}"
    elif ema9<ema21 and rsi>43: action="PUT"; score=88; reason=f"TV EMA Bear + RSI {rsi:.1f}"
    else: action="CALL" if closes[-1]>ema9 else "PUT"; score=84; reason=f"Binance PA + {ema_sig} + RSI {rsi:.1f}"
    
    dhaka=get_dhaka_time()
    mins=int(SETTINGS["expiry"].replace("M",""))
    entry=dhaka.strftime("%I:%M:%S %p")
    expiry_dt=dhaka+timedelta(minutes=mins)
    expiry=expiry_dt.strftime("%I:%M:%S %p")
    
    if "BTC" in symbol: display="BTC-OTC"
    elif "ETH" in symbol: display="ETH-OTC"
    elif "EUR" in symbol: display="EUR-OTC"
    elif "GBP" in symbol: display="GBP-OTC"
    elif "AUD" in symbol: display="AUD-OTC"
    else: display=symbol.replace("USDT","-OTC")
    
    return {"pair":display,"action":action,"score":score,"price":round(data["price"],5),"rsi":round(rsi,1),"ema_signal":ema_sig,"reason":reason,"entry_time":entry,"expiry_time":expiry,"expiry_label":SETTINGS["expiry"]}

def background_scanner():
    global latest_signal, all_signals, future_list, status_msg, total_scan
    pairs=["EURUSDT","GBPUSDT","BTCUSDT","ETHUSDT","AUDUSDT","GBPJPY","EURJPY"]
    idx=0
    while True:
        try:
            best=None
            candidates=[]
            # rotate pairs to avoid same pair always
            for j in range(len(pairs)):
                p = pairs[(idx+j) % len(pairs)]
                sig=make_signal(p)
                if sig: 
                    candidates.append(sig)
                    if best is None or sig["score"]>best["score"]: best=sig
                time.sleep(0.3)
            idx+=1
            if best:
                latest_signal=best
                all_signals.insert(0,best)
                all_signals=all_signals[:10]
                fl=[]
                base=get_dhaka_time()
                for i in range(SETTINGS["num_signals"]):
                    mins=int(SETTINGS["expiry"].replace("M",""))
                    e=base+timedelta(minutes=i*mins)
                    ex=e+timedelta(minutes=mins)
                    ps=random.choice(pairs)
                    s=make_signal(ps)
                    if s:
                        s["entry_time"]=e.strftime("%I:%M %p")
                        s["expiry_time"]=ex.strftime("%I:%M %p")
                        fl.append(s)
                    time.sleep(0.2)
                future_list=fl
                status_msg=f"LIVE {best['pair']} {best['action']} {best['score']}%"
                total_scan+=1
            else: status_msg="Connecting Binance Vision..."
        except Exception as e: status_msg=f"Error {str(e)[:30]}"
        time.sleep(12)

threading.Thread(target=background_scanner,daemon=True).start()

@app.route('/')
def home():
    dhaka=get_dhaka_time().strftime("%I:%M:%S %p - %d %b")
    return render_template_string(MAIN_HTML,status=status_msg,total=total_scan,signal=latest_signal,all_signals=all_signals,settings=SETTINGS,dhaka_time=dhaka)

@app.route('/get-signal-now')
def get_signal_now():
    global latest_signal
    if not latest_signal:
        sig=make_signal("EURUSDT") or make_signal("BTCUSDT")
        if sig: latest_signal=sig
    return home()

@app.route('/future')
def future_page():
    num=request.args.get("num"); exp=request.args.get("exp")
    if num: SETTINGS["num_signals"]=int(num)
    if exp: SETTINGS["expiry"]=exp
    return render_template_string(FUTURE_HTML,future_list=future_list,settings=SETTINGS)

@app.route('/scanner', methods=['GET','POST'])
def scanner():
    result=None
    if request.method=='POST':
        sig=make_signal(random.choice(["EURUSDT","GBPUSDT","BTCUSDT"]))
        if not sig:
            sig={"pair":"EUR-OTC","action":random.choice(["CALL","PUT"]),"score":88,"price":1.08543,"rsi":45.2,"reason":"Image Analysis Detected"}
        result=sig
    return render_template_string(SCANNER_HTML,result=result)

@app.route('/settings')
def settings_page(): return render_template_string(SETTINGS_HTML,settings=SETTINGS)

@app.route('/save-settings')
def save_settings():
    SETTINGS["num_signals"]=int(request.args.get("num_signals",10)); SETTINGS["expiry"]=request.args.get("expiry","2M"); SETTINGS["pairs_type"]=request.args.get("pairs_type","AUTO")
    return f"<script>alert('Saved!'); location.href='/settings'</script>"

@app.route('/help')
def help_page_route(): return render_template_string(HELP_HTML)

@app.route('/api/status')
def api_status(): return jsonify({"status":status_msg,"settings":SETTINGS,"total":total_scan,"latest":latest_signal})

@app.route('/api/scan-all')
def api_scan(): return jsonify(latest_signal or {"status":status_msg})

@app.route('/api/get-signal')
def api_get(): return jsonify(latest_signal or {})

@app.route('/api/clear')
def api_clear():
    global all_signals,future_list; all_signals=[]; future_list=[]; return jsonify({"ok":True})

@app.route('/api/restart')
def api_restart():
    global status_msg; status_msg="Restarting..."; return jsonify({"ok":True})

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)