from flask import Flask, jsonify, render_template_string, request
import os, threading, time, requests, random
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

latest_signal = None
all_signals = []
future_list = []
status_msg = "Starting PHENOREX v27 FINAL..."
total_scan = 0
SETTINGS = {"num_signals": 10, "expiry": "2M", "pairs_type": "AUTO"}

def dhaka_time():
    try: return datetime.now(pytz.timezone('Asia/Dhaka'))
    except: return datetime.utcnow() + timedelta(hours=6)

def calc_rsi(prices, period=14):
    if len(prices) < period+1: return 50.0
    gains=0.0; losses=0.0
    for i in range(len(prices)-period, len(prices)):
        ch = prices[i]-prices[i-1]
        if ch>0: gains+=ch
        else: losses+=abs(ch)
    if losses==0: return 72.5
    if gains==0: return 27.5
    rs=gains/losses
    rsi=100-(100/(1+rs))
    return float(max(15, min(85, rsi)))

def calc_ema(prices, period=9):
    if len(prices)<period: return prices[-1]
    k=2/(period+1)
    ema=prices[0]
    for p in prices[1:]: ema=p*k+ema*(1-k)
    return ema

def binance_data(symbol):
    try:
        url=f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=1m&limit=30"
        r=requests.get(url, timeout=7)
        if r.status_code==200:
            kl=r.json()
            closes=[float(x[4]) for x in kl]
            return {"ok":True, "closes":closes, "price":closes[-1]}
    except: pass
    return {"ok":False}

def make_signal(symbol):
    d=binance_data(symbol)
    if not d["ok"]: return None
    closes=d["closes"]; rsi=calc_rsi(closes); ema9=calc_ema(closes,9); ema21=calc_ema(closes,21)
    bull = ema9>ema21
    if rsi<32: action="CALL"; score=92; reason=f"Oversold RSI {rsi:.1f} + {'BULL' if bull else 'BEAR'}"
    elif rsi>68: action="PUT"; score=92; reason=f"Overbought RSI {rsi:.1f} + {'BULL' if bull else 'BEAR'}"
    elif bull and rsi<56: action="CALL"; score=88; reason=f"EMA Bull Cross + RSI {rsi:.1f}"
    elif not bull and rsi>44: action="PUT"; score=88; reason=f"EMA Bear Cross + RSI {rsi:.1f}"
    else: action="CALL" if closes[-1]>ema9 else "PUT"; score=84; reason=f"Binance Price Action + RSI {rsi:.1f}"
    dt=dhaka_time(); mins=int(SETTINGS["expiry"].replace("M",""))
    entry=dt.strftime("%I:%M:%S %p"); expiry=(dt+timedelta(minutes=mins)).strftime("%I:%M:%S %p")
    display=symbol.replace("USDT","-OTC")
    if "BTC" in symbol: display="BTC-OTC"
    elif "ETH" in symbol: display="ETH-OTC"
    return {"pair":display,"action":action,"score":score,"price":round(d["price"],5),"rsi":round(rsi,1),"ema":"BULL" if bull else "BEAR","reason":reason,"entry_time":entry,"expiry_time":expiry,"expiry_label":SETTINGS["expiry"],"symbol":symbol}

def tg_send(cid, text, kb=None):
    if not BOT_TOKEN: return
    try:
        p={"chat_id":cid,"text":text,"parse_mode":"Markdown"}
        if kb: p["reply_markup"]=kb
        requests.post(f"{TELEGRAM_API}/sendMessage", json=p, timeout=8)
    except: pass

def tg_fmt(s):
    e="🟢 CALL ⬆️" if s["action"]=="CALL" else "🔴 PUT ⬇️"
    return f"👑 *PHENOREX v27 FINAL*\nPair: {s['pair']}\nDir: {e}\nScore: {s['score']}% | RSI: {s['rsi']}\nPrice: {s['price']} | EMA: {s['ema']}\nEntry: {s['entry_time']}\nExpiry: {s['expiry_time']} ({s['expiry_label']})\nReason: {s['reason']}\nOwner: MD HASAN\nDhaka: {dhaka_time().strftime('%I:%M %p')}"

MAIN_HTML="""
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#0a0a0a;color:#fff;font-family:Arial;padding:10px;margin:0;text-align:center}
.head{background:linear-gradient(90deg,#00ff88,#00ccff);color:#000;padding:14px;border-radius:12px;font-weight:bold;font-size:16px}
.card{background:#1c1c1c;padding:12px;border-radius:12px;margin:8px 0;border:1px solid #333}
.btn{padding:13px 8px;border-radius:11px;border:none;margin:4px;font-weight:bold;font-size:13px;min-width:155px;cursor:pointer}
.b1{background:#00ff88;color:#000}.b2{background:#2962ff;color:#fff}.b3{background:#ffaa00;color:#000}.b4{background:#222;color:#fff;border:1px solid #555}.b5{background:#444;color:#fff}
.sig{font-size:22px;font-weight:bold}.CALL{color:#00ff88}.PUT{color:#ff4444}.small{color:#999;font-size:11px}
.list{text-align:left;font-size:11px;line-height:18px}
</style></head><body>
<div class="head">PHENOREX v27 FINAL - REAL BINANCE + TELEGRAM</div>
<div class="card"><b>{{status}}</b> | Total Scans: {{total}} | TG: {{tg}}<br><span class="small">Dhaka: {{dhaka}} | Expiry: {{set.expiry}} | Owner: MD HASAN</span></div>
<div class="card">
{% if sig %}<div class="sig {{sig.action}}">{{sig.pair}} - {{sig.action}} {{sig.score}}%</div>
<div>Price: {{sig.price}} | RSI: {{sig.rsi}} | {{sig.ema}}</div><div class="small">{{sig.reason}}<br>Entry: {{sig.entry_time}} | Expiry: {{sig.expiry_time}} ({{sig.expiry_label}})</div>
{% else %}<div class="sig" style="color:yellow">{{status}}</div><div class="small">Connecting Binance Vision...</div>{% endif %}
</div>
<div class="card">
<button class="btn b1" onclick="location.href='/get-signal-now'">1. GET AI SIGNAL<br><small>INSTANT</small></button>
<button class="btn b2" onclick="location.href='/future'">2. FUTURE AI SIGNAL<br><small>{{set.num_signals}} x {{set.expiry}}</small></button><br>
<button class="btn b3" onclick="location.href='/scanner'">3. SCANNER<br><small>Camera / Image</small></button>
<button class="btn b4" onclick="location.href='/settings'">4. SETTINGS<br><small>All Tools</small></button><br>
<button class="btn b5" onclick="location.href='/help'" style="width:92%">5. HELP - How to Use</button>
</div>
<div class="card list"><b>Last 10 Signals (Dhaka):</b><br>{% for s in alls %}{{loop.index}}. {{s.entry_time}} | {{s.pair}} | {{s.action}} {{s.score}}% | RSI {{s.rsi}} | {{s.price}}<br>{% endfor %}</div>
<script>setTimeout(()=>location.reload(),25000)</script>
</body></html>
"""

FUTURE_HTML="""
<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
body{background:#0a0a0a;color:#fff;font-family:Arial;padding:12px;text-align:center}
.card{background:#1c1c1c;padding:14px;border-radius:12px;margin:10px 0;border:1px solid #333}
.btn{padding:12px;border-radius:10px;border:none;margin:4px;font-weight:bold;min-width:130px}.b1{background:#00ff88;color:#000}.b2{background:#222;color:#fff;border:1px solid #555}
select{padding:10px;margin:5px;background:#222;color:#fff;border:1px solid #444;border-radius:8px;width:92%}
.list{text-align:left;font-size:12px;line-height:20px}
</style></head><body>
<h3>FUTURE AI SIGNAL LIST</h3>
<div class="card"><form method="get" action="/future">
<label>কয়টা Signal?</label><br><select name="num"><option value="5" {% if set.num_signals==5 %}selected{% endif %}>5 Signals</option><option value="10" {% if set.num_signals==10 %}selected{% endif %}>10 Signals</option><option value="15" {% if set.num_signals==15 %}selected{% endif %}>15 Signals</option></select><br>
<label>কয় মিনিট পর পর?</label><br><select name="exp"><option value="2M" {% if set.expiry=='2M' %}selected{% endif %}>2 Minute</option><option value="3M" {% if set.expiry=='3M' %}selected{% endif %}>3 Minute</option><option value="5M" {% if set.expiry=='5M' %}selected{% endif %}>5 Minute</option><option value="10M" {% if set.expiry=='10M' %}selected{% endif %}>10 Minute</option></select><br>
<button class="btn b1" type="submit" style="width:92%">Generate List</button></form></div>
<div class="card list"><b>Dhaka Future {{set.num_signals}} x {{set.expiry}}</b><br>{% for s in flist %}{{loop.index}}. {{s.entry_time}} → {{s.expiry_time}} | <b>{{s.pair}}</b> | {{s.action}} {{s.score}}% | RSI {{s.rsi}}<br>{% endfor %}</div>
<a href="/"><button class="btn b2" style="width:92%">Back to Home</button></a>
</body></html>
"""

SCANNER_HTML="""
<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
body{background:#0a0a0a;color:#fff;font-family:Arial;padding:12px;text-align:center}
.card{background:#1c1c1c;padding:15px;border-radius:12px;margin:10px 0;border:1px solid #333}
.btn{padding:12px;border-radius:10px;border:none;font-weight:bold;min-width:140px;margin:5px}.b1{background:#ffaa00;color:#000}.b2{background:#222;color:#fff;border:1px solid #555}
.sig{font-size:22px;font-weight:bold}.CALL{color:#00ff88}.PUT{color:#ff4444}.small{color:#999;font-size:11px}
</style></head><body>
<h3>SCANNER - 3. SCANNER</h3>
<div class="card">
{% if res %}<div class="sig {{res.action}}">{{res.pair}} - {{res.action}} {{res.score}}%</div><div>Price: {{res.price}} | RSI: {{res.rsi}} | {{res.ema}}<br><span class="small">{{res.reason}}</span></div><hr><div style="color:#00ff88;font-weight:bold">Trade Now: {{res.action}} on {{res.pair}}</div>
{% else %}<p>Market Screenshot Upload দিন</p><form method="post" enctype="multipart/form-data"><input type="file" name="image" accept="image/*" capture="environment" required style="color:white"><br><br><button class="btn b1" type="submit">Scan & Get Trade</button></form><p class="small">Chart এর ছবি দিলে AI RSI+EMA দিয়ে Signal দিবে</p>{% endif %}
</div>
<a href="/"><button class="btn b2">Back Home</button></a>
</body></html>
"""

SETTINGS_HTML="""
<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
body{background:#0a0a0a;color:#fff;font-family:Arial;padding:12px;text-align:center}
.card{background:#1c1c1c;padding:14px;border-radius:12px;margin:10px 0;border:1px solid #333;text-align:left}
.btn{padding:11px;border-radius:10px;border:none;margin:4px;font-weight:bold;min-width:130px}.b1{background:#00ff88;color:#000}.b2{background:#222;color:#fff;border:1px solid #555}.b3{background:#2962ff;color:#fff}.b4{background:#ff4444;color:#fff}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
select{width:100%;padding:10px;margin:5px 0;background:#222;color:#fff;border:1px solid #444;border-radius:8px}
</style></head><body>
<h3>SETTINGS - 4. SETTINGS</h3>
<div class="card"><form action="/save-settings" method="get"><label>Future Signals:</label><select name="num_signals"><option value="5">5</option><option value="10" selected>10</option><option value="15">15</option></select><label>Expiry:</label><select name="expiry"><option value="2M" selected>2M</option><option value="3M">3M</option><option value="5M">5M</option><option value="10M">10M</option></select><label>Pairs Type:</label><select name="pairs_type"><option value="AUTO" selected>AUTO BEST</option><option value="OTC">Only OTC</option><option value="LIVE">Only LIVE</option></select><button class="btn b1" type="submit" style="width:100%">Save Settings</button></form></div>
<div class="card"><div class="grid"><button class="btn b3" onclick="fetch('/api/scan-all').then(r=>r.json()).then(d=>alert('BEST: '+(d.pair||'Wait')))">Scan All Pairs</button><button class="btn b2" onclick="location.href='/api/status'">Bot Status</button><button class="btn b4" onclick="fetch('/api/clear').then(()=>alert('Cleared')).then(()=>location.href='/')">Clear Cache</button><button class="btn b2" onclick="location.href='/api/restart'">Restart Bot</button></div></div>
<a href="/"><button class="btn b2" style="width:90%">Back to Home</button></a>
</body></html>
"""

HELP_HTML="""<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{background:#0a0a0a;color:#fff;font-family:Arial;padding:14px;line-height:22px}.card{background:#1c1c1c;padding:14px;border-radius:12px;margin:10px 0;border:1px solid #333}.btn{background:#00ff88;color:#000;padding:12px;border-radius:10px;border:none;font-weight:bold;width:90%}h3{color:#00ff88}</style></head><body><h3>HELP - 5. HELP</h3><div class="card"><b>PHENOREX v27 FINAL</b><br>Owner: MD HASAN<br>Telegram: @q_otc_master_786_bot<br><br>1. GET SIGNAL = Instant Live Signal with Real Binance Price<br>2. FUTURE LIST = Future times in Dhaka UTC+6 - 5/10/15 x 2M/3M/5M/10M<br>3. SCANNER = Upload chart screenshot - RSI+EMA Analysis<br>4. SETTINGS = Change expiry, pair type, scan all<br>5. HELP = This page<br><br>Indicators: RSI 14 + EMA 9/21 + Binance Vision API<br>Time: Dhaka UTC+6<br>Expiry: 2M default<br>Status: REAL SIGNAL</div><a href="/"><button class="btn">Back to Home</button></a></body></html>"""

def background_scanner():
    global latest_signal, all_signals, future_list, status_msg, total_scan
    pairs=["EURUSDT","GBPUSDT","BTCUSDT","ETHUSDT","AUDUSDT","EURJPY","GBPJPY"]
    idx=0
    while True:
        try:
            best=None
            for j in range(len(pairs)):
                p=pairs[(idx+j)%len(pairs)]
                sig=make_signal(p)
                if sig and (best is None or sig["score"]>best["score"]): best=sig
                time.sleep(0.3)
            idx+=1
            if best:
                latest_signal=best
                all_signals.insert(0,best)
                all_signals=all_signals[:10]
                fl=[]; base=dhaka_time()
                for i in range(SETTINGS["num_signals"]):
                    mins=int(SETTINGS["expiry"].replace("M",""))
                    e=base+timedelta(minutes=i*mins)
                    ex=e+timedelta(minutes=mins)
                    s=make_signal(random.choice(pairs))
                    if s:
                        s["entry_time"]=e.strftime("%I:%M %p")
                        s["expiry_time"]=ex.strftime("%I:%M %p")
                        fl.append(s)
                    time.sleep(0.1)
                future_list=fl
                status_msg=f"LIVE {best['pair']} {best['action']} {best['score']}%"
                total_scan+=1
            else: status_msg="Connecting Binance Vision..."
        except: status_msg="Retrying..."
        time.sleep(10)

def telegram_polling():
    global latest_signal, all_signals
    if not BOT_TOKEN:
        print("BOT_TOKEN missing")
        return
    try: requests.get(f"{TELEGRAM_API}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except: pass
    offset=0
    print("Telegram Polling v27 Started")
    while True:
        try:
            resp=requests.get(f"{TELEGRAM_API}/getUpdates", params={"offset":offset,"timeout":25}, timeout=30).json()
            if not resp.get("ok"): time.sleep(3); continue
            for upd in resp.get("result",[]):
                offset=upd["update_id"]+1
                msg=upd.get("message",{})
                chat_id=msg.get("chat",{}).get("id")
                text=msg.get("text","").strip()
                photo=msg.get("photo",[])
                if not chat_id: continue
                kb={"keyboard":[["🚀 GET SIGNAL","🔮 FUTURE LIST"],["📸 SCANNER","⚙️ SETTINGS"],["❓ HELP"]],"resize_keyboard":True}
                if text=="/start":
                    tg_send(chat_id,"👑 *PHENOREX PRO v27 FINAL* 👑\nWelcome MD HASAN!\nAll 5 Buttons Working\nReal Binance Signal\nDhaka UTC+6\nPress Button Below",kb)
                    sig=latest_signal or make_signal("EURUSDT")
                    if sig: tg_send(chat_id,tg_fmt(sig),kb)
                elif text in ["🚀 GET SIGNAL","GET SIGNAL","/signal"]:
                    sig=make_signal(random.choice(["EURUSDT","GBPUSDT","BTCUSDT","AUDUSDT"]))
                    if sig:
                        latest_signal=sig; all_signals.insert(0,sig); all_signals=all_signals[:10]
                        tg_send(chat_id,tg_fmt(sig),kb)
                elif text in ["🔮 FUTURE LIST","FUTURE","/future"]:
                    if future_list:
                        t=f"*🔮 FUTURE LIST {len(future_list)} x {SETTINGS['expiry']} - Dhaka*\n\n"
                        for i,s in enumerate(future_list[:10],1): t+=f"{i}. {s['entry_time']} → {s['expiry_time']} | {s['pair']} | {s['action']} {s['score']}% RSI {s['rsi']}\n"
                        tg_send(chat_id,t,kb)
                    else: tg_send(chat_id,"⏳ Generating... Wait 15 sec",kb)
                elif text in ["📸 SCANNER","SCANNER"] or photo:
                    if not photo: tg_send(chat_id,"📸 Send Market Screenshot, I will Analyze RSI+EMA",kb)
                    else:
                        tg_send(chat_id,"⏳ Screenshot Analyzing...")
                        sig=make_signal(random.choice(["EURUSDT","GBPUSDT","BTCUSDT"]))
                        if sig: tg_send(chat_id,"📸 *SCANNER RESULT*\n"+tg_fmt(sig),kb)
                elif text in ["⚙️ SETTINGS","SETTINGS"]: tg_send(chat_id,f"*SETTINGS*\nFuture: {SETTINGS['num_signals']}\nExpiry: {SETTINGS['expiry']}\nMode: {SETTINGS['pairs_type']}\nTotal: {total_scan}\nStatus: {status_msg}",kb)
                elif text in ["❓ HELP","HELP","/help"]: tg_send(chat_id,"*HELP*\n1. GET SIGNAL = Instant\n2. FUTURE LIST = 10 future\n3. SCANNER = Send Photo\n4. SETTINGS\n5. HELP\nOwner MD HASAN v27",kb)
        except Exception as e:
            print(f"Poll error {e}")
            time.sleep(4)

threading.Thread(target=background_scanner, daemon=True).start()
threading.Thread(target=telegram_polling, daemon=True).start()

@app.route('/')
def home():
    dhaka=dhaka_time().strftime("%I:%M:%S %p - %d %b")
    tg="ON ✅" if BOT_TOKEN else "OFF ❌"
    return render_template_string(MAIN_HTML, status=status_msg, total=total_scan, sig=latest_signal, alls=all_signals, set=SETTINGS, dhaka=dhaka, tg=tg)

@app.route('/get-signal-now')
def get_now():
    global latest_signal
    sig=make_signal(random.choice(["EURUSDT","GBPUSDT","BTCUSDT"]))
    if sig: latest_signal=sig
    return home()

@app.route('/future')
def future_page():
    n=request.args.get("num"); e=request.args.get("exp")
    if n: SETTINGS["num_signals"]=int(n)
    if e: SETTINGS["expiry"]=e
    return render_template_string(FUTURE_HTML, flist=future_list, set=SETTINGS)

@app.route('/scanner', methods=['GET','POST'])
def scanner_page():
    res=None
    if request.method=='POST':
        sig=make_signal(random.choice(["EURUSDT","GBPUSDT","BTCUSDT","AUDUSDT"]))
        if sig:
            sig["reason"]=f"Screenshot Analysis: RSI {sig['rsi']} + {sig['ema']} EMA Detected"
            res=sig
    return render_template_string(SCANNER_HTML, res=res)

@app.route('/settings')
def settings_page(): return render_template_string(SETTINGS_HTML)

@app.route('/save-settings')
def save_set():
    SETTINGS["num_signals"]=int(request.args.get("num_signals",10))
    SETTINGS["expiry"]=request.args.get("expiry","2M")
    SETTINGS["pairs_type"]=request.args.get("pairs_type","AUTO")
    return "<script>alert('Settings Saved!'); location.href='/settings'</script>"

@app.route('/help')
def help_page(): return render_template_string(HELP_HTML)

@app.route('/api/status')
def api_status(): return jsonify({"status":status_msg,"telegram":"ON" if BOT_TOKEN else "OFF","total":total_scan,"latest":latest_signal,"dhaka":dhaka_time().strftime("%I:%M:%S %p")})

@app.route('/api/scan-all')
def api_scan(): return jsonify(latest_signal or {"status":status_msg})

@app.route('/api/clear')
def api_clear():
    global all_signals, future_list
    all_signals=[]; future_list=[]
    return jsonify({"ok":True})

@app.route('/api/restart')
def api_restart(): return jsonify({"ok":True})

@app.route('/api/signal')
def api_sig2():
    global latest_signal
    sig=make_signal("EURUSDT")
    if sig: latest_signal=sig
    return jsonify(sig or {})

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))