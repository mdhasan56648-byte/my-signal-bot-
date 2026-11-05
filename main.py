import os
from flask import Flask
import threading
import telebot, random, time
from datetime import datetime, timedelta
from telebot import types

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN, threaded=False)

PAIRS = ["USD/BRL-OTC","USD/MXN-OTC","EUR/JPY-OTC","CAD/CHF-OTC","USD/BDT-OTC","USD/EGP-OTC","USD/PKR-OTC","USD/ZAR-OTC","USD/INR-OTC"]

def bdf():
    return datetime.utcnow() + timedelta(hours=6)

try:
    bot.delete_webhook(drop_pending_updates=True)
    time.sleep(2)
except:
    pass

@bot.message_handler(commands=['start'])
def start(m):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("BEST TRADE", "FUTURE LIST")
    kb.row("STATS", "HELP")
    bot.send_message(m.chat.id, "MD Hasan v17 SECURE 24/7 READY!\nUpper Timeframe 1m/2m", reply_markup=kb)

@bot.message_handler(func=lambda m: True)
def all_msg(m):
    t = (m.text or "").upper()
    if "BEST" in t:
        p = random.choice(PAIRS)
        d = random.choice(["UP","DOWN"])
        ent = (bdf()+timedelta(minutes=1)).strftime("%I:%M %p")
        cur = bdf().strftime("%I:%M %p")
        out = f"🚀 {p} ➤ {d} ➤ {random.randint(95,99)}%\n⏰ UP: {cur} - DOWN: {cur}\n📍 {p} ➤ {d}\n⏱️ 1/100\nEntry: {ent} BD"
        bot.send_message(m.chat.id, out)
    elif "FUTURE" in t:
        cur = bdf()+timedelta(minutes=1)
        out = "🔮 FUTURE 10x2M DHAKA\n"
        for i in range(10):
            p = random.choice(PAIRS)
            d = random.choice(["UP","DOWN"])
            out += f"{i+1}. {cur.strftime('%I:%M %p')} - {p.replace('-OTC','')} - {d}\n"
            cur += timedelta(minutes=2)
        bot.send_message(m.chat.id, out)
    else:
        start(m)

print("Running")
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except:
        time.sleep(3)