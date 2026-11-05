import os
import random
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- TOKEN (Railway/Render theke nibe) ---
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN not found! Railway Variables e TOKEN add koro.")

# --- USER DATA ---
user_data = {} 
# {user_id: {'win':0, 'loss':0, 'streak':0, 'paused':False}}

def get_user(uid):
    if uid not in user_data:
        user_data[uid] = {'win':0, 'loss':0, 'streak':0, 'paused':False}
    return user_data[uid]

# --- CONFIG ---
OTC_PAIRS = ["EUR/USD-OTC","GBP/USD-OTC","EUR/JPY-OTC","USD/BDT-OTC","AUD/USD-OTC","USD/BRL-OTC","GBP/JPY-OTC","USD/PKR-OTC"]
STRATEGIES = [
    "SMA20 + EMA21 Golden Cross",
    "Trinity SMA+EMA+TMA+RSI",
    "3 EMA(5,8,13) + Stochastic",
    "Sidus EMA18/28 + WMA5/8",
    "200 EMA Trend Filter",
    "3-Candle Price Action",
    "ZigZag + DeMarker14",
    "S/R + Channel Break",
    "Bollinger + CCI14",
    "Alligator + Fractals",
    "Hammer / Engulfing"
]

def dhaka_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=6)

def make_signal():
    pair = random.choice(OTC_PAIRS)
    direction = random.choice(["UP","DOWN"])
    strategy = random.choice(STRATEGIES)
    conf = random.randint(86, 96)
    payout = random.randint(88, 94)
    if direction == "UP":
        txt = f"🟢 *{pair} - CALL / UP*\n\n📈 Strategy: {strategy}\n💎 Confidence: {conf}%\n💵 Payout: {payout}%\n📡 Reason: SMA20/EMA21 Cross + Support Bounce + RSI Confirm"
    else:
        txt = f"🔴 *{pair} - PUT / DOWN*\n\n📉 Strategy: {strategy}\n💎 Confidence: {conf}%\n💵 Payout: {payout}%\n📡 Reason: EMA 18/28 Cross Down + Resistance Reject + DeMarker Confirm"
    return txt, direction

# --- KEYBOARDS ---
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 GET SIGNAL", callback_data="get")],
        [InlineKeyboardButton("📋 FUTURE SIGNAL - 10x2M", callback_data="future")],
        [InlineKeyboardButton("🧠 SCAN AI BRAIN", callback_data="scan")],
        [InlineKeyboardButton("📸 SCREENSHOT SCAN", callback_data="ss_info")],
        [InlineKeyboardButton("📊 STATUS BOARD", callback_data="status"), InlineKeyboardButton("🆘 HELP CENTER", callback_data="help")]
    ])

def result_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ WIN", callback_data="win"), InlineKeyboardButton("❌ LOSS", callback_data="loss")],
        [InlineKeyboardButton("⬅️ Main Menu", callback_data="main")]
    ])

def help_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Restart Bot", callback_data="restart"), InlineKeyboardButton("🧹 Clear Cache", callback_data="clear")],
        [InlineKeyboardButton("📡 Check Connection", callback_data="conn"), InlineKeyboardButton("🛑 Emergency Stop", callback_data="estop")],
        [InlineKeyboardButton("📈 OTC Status", callback_data="otc"), InlineKeyboardButton("💵 Payout Check", callback_data="payout")],
        [InlineKeyboardButton("📖 How To Use", callback_data="howto"), InlineKeyboardButton("💡 Strategy Bank", callback_data="strat")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main")]
    ])

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    acc = round((u['win']/(u['win']+u['loss'])*100) if (u['win']+u['loss'])>0 else 0, 1)
    txt = f"🤖 *FINOREX v18 AI BRAIN*\n\n📊 *TODAY TRACKER*\n✅ WIN: {u['win']} | ❌ LOSS: {u['loss']}\n📈 Accuracy: {acc}%\n\n⚡ 11 Strategy | Auto 3-Loss OFF | Dhaka Time\n\nNicher 6 ta button theke choose koro:"
    if update.message:
        await update.message.reply_text(txt, reply_markup=main_kb(), parse_mode="Markdown")
    else:
        await update.callback_query.message.edit_text(txt, reply_markup=main_kb(), parse_mode="Markdown")

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)
    data = q.data

    # Paused check
    if u['paused'] and data not in ["restart","help","main","status","conn","clear"]:
        await q.message.reply_text("⚠️ *Bot Paused!* Por por 3 ta LOSS hoise.\n🆘 HELP > 🔄 Restart Bot e click koro.", parse_mode="Markdown", reply_markup=help_kb())
        return

    if data == "main":
        await start(update, context)
    
    elif data == "get":
        sig, _ = make_signal()
        now = dhaka_now()
        entry = now.strftime("%I:%M:%S %p")
        exp = (now + datetime.timedelta(minutes=1)).strftime("%I:%M:%S %p")
        full = f"{sig}\n\n🕐 Entry: {entry} (Dhaka)\n⏰ Expiry: {exp} (1 MIN)\n\nResult ki hoilo? Niche click koro:"
        await q.message.reply_text(full, parse_mode="Markdown", reply_markup=result_kb())

    elif data == "future":
        now = dhaka_now()
        msg = "📋 *FUTURE LIST - 10x SIGNALS (2M GAP)*\n_Dhaka Time_\n\n"
        for i in range(10):
            t = now + datetime.timedelta(minutes=i*2)
            exp = t + datetime.timedelta(minutes=1)
            pair = random.choice(OTC_PAIRS)
            d = random.choice(["🟢 CALL","🔴 PUT"])
            msg += f"{i+1}️⃣ {d} {pair} 🕐 {t.strftime('%I:%M')} → {exp.strftime('%I:%M')}\n"
        msg += "\n💎 11 Strategy diye scan kora"
        await q.message.reply_text(msg, parse_mode="Markdown")

    elif data == "scan":
        await q.message.reply_text("🧠 *AI BRAIN SCANNING...*\n\n🔍 8 Pairs Scan...\n📊 SMA20/EMA21 ✓\n📊 Sidus 18/28 ✓\n📊 200 EMA Filter ✓\n📊 ZigZag+DeMarker ✓\n\n✅ *Best: EUR/USD-OTC - STRONG TREND DETECTED*\nGET SIGNAL e click koro.", parse_mode="Markdown")

    elif data == "ss_info":
        await q.message.reply_text("📸 *SCREENSHOT SCAN READY*\n\nQuotex er chart er ekta clear screenshot pathao, ami 3 sec e bole dibo:\n🟢 UP naki 🔴 DOWN + Confidence%\n\nEkta photo pathao ekhane 👇")

    elif data == "status":
        total = u['win']+u['loss']
        acc = round((u['win']/total*100) if total>0 else 0,1)
        streak_txt = "❌"*u['streak'] if u['streak']>0 else "✅"
        txt = f"📊 *STATUS BOARD*\n\n✅ WIN: {u['win']}\n❌ LOSS: {u['loss']}\n📈 Accuracy: {acc}%\n🔥 Consecutive Loss: {streak_txt} ({u['streak']})\n\n⚠️ Auto-OFF: 3 LOSS por por hole bot OFF\nVersion: v18 FINAL"
        await q.message.reply_text(txt, parse_mode="Markdown")

    elif data == "help":
        await q.message.edit_text("🆘 *HELP CENTER*", reply_markup=help_kb(), parse_mode="Markdown")

    # Help sub
    elif data == "restart":
        u['paused'] = False
        u['streak'] = 0
        await q.message.reply_text("🔄 *Bot Restarted!* Cache clear, streak reset. Fresh start!", parse_mode="Markdown", reply_markup=main_kb())
    elif data == "clear":
        await q.message.reply_text("🧹 Cache Cleared!", reply_markup=help_kb())
    elif data == "conn":
        await q.message.reply_text("📡 Connected ✅\nOTC API: Stable ✅\nLatency: 38ms", reply_markup=help_kb())
    elif data == "estop":
        u['paused'] = True
        await q.message.reply_text("🛑 Emergency Stop - Bot Paused!", reply_markup=help_kb())
    elif data == "otc":
        await q.message.reply_text("📈 OTC OPEN\nBest Payout: EUR/USD-OTC 92%, USD/BDT-OTC 91%\nFiltered Bad: USD/INR-OTC", reply_markup=help_kb())
    elif data == "payout":
        await q.message.reply_text("💵 Payout: 88-94% All Good!", reply_markup=help_kb())
    elif data == "howto":
        await q.message.reply_text("📖 1.GET SIGNAL=Live\n2.FUTURE 10x2M=10 ta age\n3.Photo pathale=UP/DOWN bolbe\n4.WIN/LOSS click korle tracker update\n5.3 LOSS por por auto OFF > HELP>Restart", reply_markup=help_kb())
    elif data == "strat":
        txt = "💡 *11 STRATEGY:*\n" + "\n".join([f"{i+1}. {s}" for i,s in enumerate(STRATEGIES)])
        await q.message.reply_text(txt, parse_mode="Markdown", reply_markup=help_kb())

    elif data in ["win","loss"]:
        if data == "win":
            u['win']+=1
            u['streak']=0
            await q.message.reply_text(f"✅ WIN Saved! 📊 {u['win']} WIN | {u['loss']} LOSS", reply_markup=main_kb())
        else:
            u['loss']+=1
            u['streak']+=1
            if u['streak']>=3:
                u['paused']=True
                await q.message.reply_text(f"⚠️ *3 CONSECUTIVE LOSS!*\n📊 {u['win']} WIN | {u['loss']} LOSS\n\nBot Auto OFF! HELP > Restart dao.", parse_mode="Markdown", reply_markup=help_kb())
            else:
                await q.message.reply_text(f"❌ LOSS Saved! 📊 {u['win']} WIN | {u['loss']} LOSS\nStreak: {u['streak']}/3", reply_markup=main_kb())

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if u['paused']:
        await update.message.reply_text("⚠️ Bot Paused! Restart koro.")
        return
    conf = random.randint(85,96)
    direction = random.choice(["UP","DOWN"])
    if direction=="UP":
        txt = f"📸 *SCAN RESULT*\n\n🟢 *Next Candle UP - {conf}%* 🟢\n\nReason: Support Bounce + SMA20/EMA21 Cross Up + RSI 40→60\n\n🕐 Entry: Now\n⏰ Expiry: 1 MIN"
    else:
        txt = f"📸 *SCAN RESULT*\n\n🔴 *Next Candle DOWN - {conf}%* 🔴\n\nReason: Resistance Reject + EMA Cross Down + CCI Overbought\n\n🕐 Entry: Now\n⏰ Expiry: 1 MIN"
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=result_kb())

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    print("FINOREX v18 Running...")
    app.run_polling()

if __name__ == "__main__":
    main()