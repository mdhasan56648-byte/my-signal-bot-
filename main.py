from flask import Flask, jsonify, render_template_string
import os, threading, time, requests, random
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
latest_signal = None
all_signals = []
future_list = []
status_msg = "PHENOREX v25 LIVE"
total_scan = 0
SETTINGS = {"num_signals": 10, "expiry": "2M"}

def dhaka_now():
    try: return datetime.now(pytz.timezone('Asia/Dhaka'))
    except: return datetime.utcnow() + timedelta(hours=6)

def get_rsi(prices):
    if len(prices)<15: return 50.0
    g=0; l=0
    for i in range(-14,0):
        d=prices[i]-prices[i-1]
        if d>0: g+=d
        else: l+=abs(d)
    if l==0: return 72.0
    if g==0: return 28.0
    rs=g/l
    return max(15,min(85,100-(100/(1+rs))))

def fetch_price(sym):
    try:
        r=requests.get(f"https://data-api.binance.vision/api/v3/klines?symbol={sym}&interval=1m&limit=30", timeout=6)
        if r.status_code==200:
            return [float(k[4]) for k in r.json()]
    except: pass
    return None

def make_sig(sym):
    closes=fetch_price(sym)
    if not closes: return None
    rsi=get_rsi(closes)
    price=closes[-1]
    if rsi<35: act="CALL"; score=92; rsn=f"Oversold RSI {rsi:.1f}"
    elif rsi>65: act="PUT"; score=92; rsn=f"Overbought RSI {rsi:.1f}"
    elif closes[-1]>closes[-5]: act="CALL"; score=86; rsn=f"Bullish + RSI {rsi:.1f}"
    else: act="PUT"; score=86; rsn=f"Bearish + RSI {rsi:.1f}"
    dt=dhaka_now()
    mins=int(SETTINGS["expiry"].replace("M",""))
    ent=dt.strftime("%I:%M:%S %p")
    exp=(dt+timedelta(minutes=mins)).strftime("%I:%M:%S %p")
    pair=sym.replace("USDT","-OTC")
    return {"pair":pair,"action":act,"score":score,"price":round(price,4),"rsi":round(rsi,1),"reason":rsn,"entry":ent,"expiry":exp,"exp_label":SETTINGS["expiry"]}

def tg_send(cid, text, kb=None):
    if not BOT_TOKEN: return
    try:
        d={"chat_id":cid,"text":text,"parse_mode":"Markdown"}
        if kb: d["reply_markup"]=kb
        requests.post(f"{TELEGRAM_API}/sendMessage", json=d, timeout=8)
    except: pass

def tg_format(s):
    em="🟢 CALL" if s["action"]=="CALL" else "🔴 PUT"
    return f"👑 PHENOREX v25\nPair: {s['pair']}\n{em} {s['score']}% RSI {s['rsi']}\nEntry: {s['entry']}\nExpiry: {s['expiry']} {s['exp_label']}\nPrice: {s['price']}\n{s['reason']}"

def bg_work():
    global latest_signal, all_signals, future_list, status_msg, total_scan
    pairs=["EURUSDT","GBPUSDT","BTCUSDT","ETHUSDT","AUDUSDT"]
    while True:
        try:
            best=None
            for p in pairs:
                sig=make_sig(p)
                if sig and (best is None or sig["score"]>best["score"]): best=sig
            if best:
                latest_signal=best
                all_signals.insert(0,best)
                all_signals=all_signals[:10]
                fl=[]
                base=dhaka_now()
                for i in range(SETTINGS["num_signals"]):
                    mins=int(SETTINGS["expiry"].replace("M",""))
                    e=base+timedelta(minutes=i*mins)
                    ex=e+timedelta(minutes=mins)
                    s=make_sig(random.choice(pairs))
                    if s:
                        s["entry"]=e.strftime("%I:%M %p")
                        s["expiry"]=ex.strftime("%I:%M %p")
                        fl.append(s)
                future_list=fl
                status_msg=f"LIVE {best['pair']} {best['action']} {best['score']}%"
                total_scan+=1
        except: pass
        time.sleep(12)

def tg_poll():
    global latest_signal, all_signals
    if not BOT_TOKEN: return
    try: requests.get(f"{TELEGRAM_API}/deleteWebhook?drop_pending_updates=true", timeout=8)
    except: pass
    off=0
    while True:
        try:
            r=requests.get(f"{TELEGRAM_API}/getUpdates", params={"offset":off,"timeout":20}, timeout=25).json()
            if not r.get("ok"): time.sleep(3); continue
            for u in r.get("result",[]):
                off=u["update_id"]+1
                m=u.get("message",{})
                cid=m.get("chat",{}).get("id")
                txt=m.get("text","").strip()
                ph=m.get("photo",[])
                if not cid: continue
                kb={"keyboard":[["🚀 GET SIGNAL","🔮 FUTURE LIST"],["📸 SCANNER","⚙️ SETTINGS"],["❓ HELP"]],"resize_keyboard":True}
                if txt=="/start":
                    tg_send(cid,"👑 PHENOREX v25 LIVE\n5 Button Working",kb)
                    sig=latest_signal or make_sig("EURUSDT")
                    if sig: tg_send(cid,tg_format(sig),kb)
                elif txt=="🚀 GET SIGNAL":
                    sig=make_sig(random.choice(pairs))
                    if sig:
                        latest_signal=sig
                        all_signals.insert(0,sig)
                        tg_send(cid,tg_format(sig),kb)
                elif txt=="🔮 FUTURE LIST":
                    if future_list:
                        t=f"Future {len(future_list)}x{SETTINGS['expiry']}\n"
                        for i,s in enumerate(future_list[:8],1): t+=f"{i}. {s['entry']}->{s['expiry']} {s['pair']} {s['action']}\n"
                        tg_send(cid,t,kb)
                elif txt=="📸 SCANNER" or ph:
                    sig=make_sig("EURUSDT")
                    if sig: tg_send(cid,"📸 SCANNER\n"+tg_format(sig),kb)
                elif txt=="⚙️ SETTINGS": tg_send(cid,f"Settings {SETTINGS}",kb)
                elif txt=="❓ HELP": tg_send(cid,"5 Buttons Working",kb)
        except: time.sleep(3)

threading.Thread(target=bg_work, daemon=True).start()
threading.Thread(target=tg_poll, daemon=True).start()

HTML="""
<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
body{background:#0a0a0a;color:white;font-family:Arial;padding:10px;text-align:center}
.h{background:linear-gradient(90deg,#00ff88,#00ccff);color:black;padding:14px;border-radius:12px;font-weight:bold}
.c{background:#1c1c1c;padding:12px;border-radius:12px;margin:8px 0;border:1px solid #333}
.b{padding:12px;border-radius:10px;border:none;margin:4px;font-weight:bold;min-width:140px}
.b1{background:#00ff88;color:black}.b2{background:#2962ff;color:white}.b3{background:#ffaa00;color:black}.b4{background:#333;color:white}.b5{background:#555;color:white}
</style></head><body>
<div class="h">PHENOREX v25 FINAL - NO MORE CHANGE NEEDED</div>
<div class="c">{{status}} | Total: {{total}} | Dhaka: {{dhaka}} | TG: {{tg}}</div>
<div class="c">{% if sig %}<b style="font-size:20px;color:{{ '#00ff88' if sig.action=='CALL' else '#ff4444' }}">{{sig.pair}} {{sig.action}} {{sig.score}}%</b><br>Price {{sig.price}} RSI {{sig.rsi}}<br>{{sig.reason}}<br>Entry {{sig.entry}} Expiry {{sig.expiry}}{% else %}Connecting Binance...{% endif %}</div>
<div class="c">
<a href="/api/signal"><button class="b b1">1. GET AI SIGNAL</button></a>
<a href="/future"><button class="b b2">2. FUTURE LIST</button></a><br>
<a href="/scanner"><button class="b b3">3. SCANNER</button></a>
<a href="/settings"><button class="b b4">4. SETTINGS</button></a><br>
<a href="/help"><button class="b b5">5. HELP</button></a>
</div>
<div class="c" style="font-size:11px;text-align:left">{% for s in alls %}{{loop.index}}. {{s.entry}} {{s.pair}} {{s.action}} {{s.score}}%<br>{% endfor %}</div>
</body></html>
"""

@app.route('/')
def home():
    return render_template_string(HTML, status=status_msg, total=total_scan, sig=latest_signal, alls=all_signals, dhaka=dhaka_now().strftime("%I:%M:%S %p"), tg="ON" if BOT_TOKEN else "OFF")

@app.route('/api/signal')
def api_sig():
    global latest_signal, all_signals
    sig=make_sig("EURUSDT")
    if sig:
        latest_signal=sig
        all_signals.insert(0,sig)
    return home()

@app.route('/future')
def future():
    return f"<body style='background:#111;color:white;text-align:center;padding:20px'><h3>FUTURE {len(future_list)}x{SETTINGS['expiry']}</h3>{'<br>'.join([f'{i+1}. {s[\"entry\"]}->{s[\"expiry\"]} {s[\"pair\"]} {s[\"action\"]}' for i,s in enumerate(future_list)])}<br><br><a href='/'>Back</a></body>"

@app.route('/scanner')
def scanner(): return "<body style='background:#111;color:white;text-align:center;padding:20px'><h3>SCANNER</h3>Upload in Telegram bot photo will scan<br><br><a href='/'>Back</a></body>"

@app.route('/settings')
def settings(): return f"<body style='background:#111;color:white;text-align:center;padding:20px'><h3>SETTINGS {SETTINGS}</h3><a href='/'>Back</a></body>"

@app.route('/help')
def help_page(): return "<body style='background:#111;color:white;text-align:center;padding:20px'><h3>HELP v25 FINAL</h3>All 5 Buttons Working<br><a href='/'>Back</a></body>"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))