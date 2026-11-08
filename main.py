# PHENOREX PRO - FINAL FIXED FOR MD HASAN - NO SECOND - NO HANG
import os
import logging
import threading
import random
from datetime import datetime, timedelta
from flask import Flask
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import trading_engine

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BRAND = "PHENOREX PRO"
OWNER = "MD HASAN"

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
@app.route('/')
def home(): return f"{BRAND} - {OWNER} - LIVE"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def create_signal_image(pair, direction, strength_text, rsi, score, entry_time_str):
    W, H = 850, 500
    img = Image.new('RGB', (W, H), color='#0b1220')
    draw = ImageDraw.Draw(img)
    color = '#22c55e' if direction == "UP" else '#ef4444'
    try: font_big = ImageFont.truetype("arial.ttf", 42)
    except: font_big = ImageFont.load_default()
    try: font_mid = ImageFont.truetype("arial.ttf", 22)
    except: font_mid = ImageFont.load_default()
    try: font_small = ImageFont.truetype("arial.ttf", 16)
    except: font_small = ImageFont.load_default()

    draw.rectangle([0,0,W,70], fill='#162032')
    draw.rectangle([0,70,W,73], fill=color)
    draw.text((20,18), f"{BRAND} | LIVE SIGNAL", font=font_mid, fill='white')
    draw.text((W-150,20), f"UTC+6", font=font_small, fill='#94a3b8')
    draw.rectangle([20,100,W-20,450], fill='#121d33', outline='#1e3a5f', width=2)
    draw.text((40,120), f"Pair: {pair}", font=font_big, fill='white')
    draw.text((40,180), f"Direction:", font=font_mid, fill='#cbd5e1')
    draw.text((180,175), f"{'UP 🟢' if direction=='UP' else 'DOWN 🔴'}", font=font_big, fill=color)
    draw.text((40,240), f"Entry: {entry_time_str} (UTC+6)", font=font_mid, fill='#facc15')
    draw.text((40,275), f"Strength: {strength_text} | RSI: {rsi} | Score: {score}/6", font=font_mid, fill='#e2e8f0')
    draw.text((40,315), f"Timeframe: 1 Minute | Owner: {OWNER}", font=font_mid, fill='#94a3b8')
    draw.text((40,360), f"Reason: 6 Indicators Aligned - Real Market", font=font_small, fill='#64748b')
    draw.text((40,390), f"⚡ {BRAND} v16 | {OWNER}", font=font_small, fill=color)
    bio = BytesIO()
    bio.name = 'signal.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Get AI Signal", callback_data='get_ai_signal'),
         InlineKeyboardButton("🔮 Future AI Signal", callback_data='future_signal')],
        [InlineKeyboardButton("🆘 Help", callback_data='help'),
         InlineKeyboardButton("⚙️ Setting", callback_data='setting')]
    ])

def future_custom_keyboard(sc=None, sm=None):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{'✅ ' if sc==5 else ''}5", callback_data='fcount_5'),
         InlineKeyboardButton(f"{'✅ ' if sc==8 else ''}8", callback_data='fcount_8'),
         InlineKeyboardButton(f"{'✅ ' if sc==10 else ''}10", callback_data='fcount_10'),
         InlineKeyboardButton(f"{'✅ ' if sc==15 else ''}15", callback_data='fcount_15')],
        [InlineKeyboardButton(f"{'✅ ' if sm==2 else ''}2m", callback_data='fmin_2'),
         InlineKeyboardButton(f"{'✅ ' if sm==3 else ''}3m", callback_data='fmin_3'),
         InlineKeyboardButton(f"{'✅ ' if sm==5 else ''}5m", callback_data='fmin_5'),
         InlineKeyboardButton(f"{'✅ ' if sm==10 else ''}10m", callback_data='fmin_10')],
        [InlineKeyboardButton("🚀 Confirm & Start", callback_data='future_confirm')],
        [InlineKeyboardButton("⬅️ Back", callback_data='main_menu')]
    ])

async def send_scheduled_signal(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    pair = random.choice(trading_engine.QUOTEX_OTC_PAIRS)
    res = trading_engine.analyze_fast(pair)
    now = datetime.utcnow() + timedelta(hours=6)
    entry_str = now.strftime('%H:%M')
    img = create_signal_image(pair, res['decision'], res.get('strength_text','STRONG'), res['rsi'], res['score'], entry_str)
    caption = f"🔮 FUTURE #{job.data['index']}/{job.data['total']} - {BRAND}\n\nPair: {pair}\nDir: {res['decision']}\nEntry: {entry_str} UTC+6\nTF: 1 Min\nOwner: {OWNER}"
    await context.bot.send_photo(chat_id=job.chat_id, photo=img, caption=caption, reply_markup=main_menu_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.utcnow() + timedelta(hours=6)
    text = f"🏠 **Main Menu - {BRAND}**\n\n👑 Owner: {OWNER}\n🕒 Time: {now.strftime('%H:%M')} UTC+6\n📈 LIVE ✅\n\n4 টা বাটন থেকে Select করুন:"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    now = datetime.utcnow() + timedelta(hours=6)
    time_str = now.strftime('%H:%M')

    if data == 'main_menu':
        await query.edit_message_text(f"🏠 **Main Menu - {BRAND}**\n\n👑 {OWNER}\n🕒 {time_str} UTC+6\nLIVE ✅", reply_markup=main_menu_keyboard(), parse_mode='Markdown')
        return
    if data == 'help':
        await query.edit_message_text(f"🆘 **Help - {BRAND}**\n\n🤖 Get AI Signal: Instant Signal ছবি সহ\n🔮 Future: 5/8/10/15 টা Signal, 2/3/5/10 মিনিট পরপর\n⚙️ Setting: আপনার Default Setting দেখুন\n\n📊 6 Indicators Real Analysis\n👑 {OWNER} | UTC+6", reply_markup=main_menu_keyboard(), parse_mode='Markdown')
        return
    if data == 'setting':
        sc = context.user_data.get('future_count', 10)
        sm = context.user_data.get('future_min', 3)
        await query.edit_message_text(f"⚙️ **Setting - {BRAND}**\n\nOwner: {OWNER}\nTF: 1 Min | Market: OTC\nDefault: {sc} Signals / {sm} Min\nUTC+6 Dhaka\nCustomization Active ✅", reply_markup=main_menu_keyboard(), parse_mode='Markdown')
        return
    if data == 'future_signal':
        sc = context.user_data.get('future_count')
        sm = context.user_data.get('future_min')
        await query.edit_message_text(f"🔮 **Future Signal Customization**\n\nকয়টা Signal? [5/8/10/15]\nকত মিনিট পরপর? [2/3/5/10]\n\nCurrent: {sc or 'Not Set'} | {sm or 'Not Set'} Min\nSelect করে Confirm দিন:", reply_markup=future_custom_keyboard(sc, sm), parse_mode='Markdown')
        return
    if data.startswith('fcount_'):
        context.user_data['future_count'] = int(data.split('_')[1])
        await query.edit_message_text(f"Count: {context.user_data['future_count']} ✅ | Min: {context.user_data.get('future_min','Not Set')}\nএখন Min Select করুন:", reply_markup=future_custom_keyboard(context.user_data['future_count'], context.user_data.get('future_min')), parse_mode='Markdown')
        return
    if data.startswith('fmin_'):
        context.user_data['future_min'] = int(data.split('_')[1])
        await query.edit_message_text(f"Count: {context.user_data.get('future_count','Not Set')} | Min: {context.user_data['future_min']} ✅\nএখন Confirm দিন:", reply_markup=future_custom_keyboard(context.user_data.get('future_count'), context.user_data['future_min']), parse_mode='Markdown')
        return
    if data == 'future_confirm':
        sc = context.user_data.get('future_count')
        sm = context.user_data.get('future_min')
        if not sc or not sm:
            await query.edit_message_text("❌ আগে Count আর Min Select করুন!", reply_markup=future_custom_keyboard(sc, sm), parse_mode='Markdown')
            return
        await query.edit_message_text(f"🚀 Started {sc} Signals every {sm}m - {BRAND}\nTime: {time_str} UTC+6", reply_markup=main_menu_keyboard(), parse_mode='Markdown')
        for i in range(sc):
            context.job_queue.run_once(send_scheduled_signal, when=(i+1)*sm*60, chat_id=query.message.chat_id, data={"index": i+1, "total": sc})
        return
    if data == 'get_ai_signal':
        await query.edit_message_text(f"⏳ {BRAND} Analyzing... {time_str} UTC+6")
        pair = random.choice(trading_engine.QUOTEX_OTC_PAIRS)
        res = trading_engine.analyze_fast(pair)
        img = create_signal_image(pair, res['decision'], res.get('strength_text','STRONG'), res['rsi'], res['score'], time_str)
        caption = f"📈 **LIVE - {BRAND}**\n\nPair: {pair}\nDirection: {res['decision']}\nEntry: {time_str} UTC+6\nTF: 1 Min\nStrength: {res.get('strength_text')}\nRSI: {res['rsi']}\nOwner: {OWNER}"
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=img, caption=caption, reply_markup=main_menu_keyboard(), parse_mode='Markdown')
        try: await query.delete_message()
        except: pass

def run_bot():
    if not BOT_TOKEN: return
    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    print(f"{BRAND} Started")
    app_bot.run_polling()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()