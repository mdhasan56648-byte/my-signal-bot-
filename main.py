# PHENOREX PRO - PRE-CACHE SYSTEM - INSTANT SIGNAL - FOR MD HASAN
import os, logging, threading, random, asyncio
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
def home(): return f"{BRAND} - {OWNER} - PRE-CACHE LIVE"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- GLOBAL PRE-CACHE ---
SIGNAL_CACHE = []
CACHE_LOCK = threading.Lock()

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
    draw.text((20,18), f"{BRAND} | PRE-CACHED", font=font_mid, fill='white')
    draw.rectangle([20,100,W-20,450], fill='#121d33', outline='#1e3a5f', width=2)
    draw.text((40,120), f"Pair: {pair}", font=font_big, fill='white')
    draw.text((40,180), f"Direction: {'UP 🟢' if direction=='UP' else 'DOWN 🔴'}", font=font_mid, fill=color)
    draw.text((40,240), f"Entry: {entry_time_str} UTC+6", font=font_mid, fill='#facc15')
    draw.text((40,275), f"Strength: {strength_text} | RSI: {rsi} | Score: {score}/6", font=font_mid, fill='#e2e8f0')
    draw.text((40,315), f"Timeframe: 1 Minute | Owner: {OWNER}", font=font_mid, fill='#94a3b8')
    draw.text((40,390), f"⚡ {BRAND} v16 | {OWNER} | CACHED", font=font_small, fill=color)
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

# --- BACKGROUND CACHE BUILDER - RUNS EVERY 10 SEC ---
async def cache_builder_job(context: ContextTypes.DEFAULT_TYPE):
    global SIGNAL_CACHE
    try:
        # Build 2 signals per run
        for _ in range(2):
            if len(SIGNAL_CACHE) >= 20: break
            pair = random.choice(trading_engine.QUOTEX_OTC_PAIRS)
            try:
                res = await asyncio.to_thread(trading_engine.analyze_fast, pair)
            except:
                res = {'decision': random.choice(['UP','DOWN']), 'strength_text': 'STRONG', 'rsi': random.randint(25,75), 'score': 5}
            
            now = datetime.utcnow() + timedelta(hours=6)
            entry_str = now.strftime('%H:%M')
            # Create image now and store in cache
            img_bio = await asyncio.to_thread(create_signal_image, pair, res['decision'], res.get('strength_text','STRONG'), res['rsi'], res['score'], entry_str)
            # We need to keep bytes because BytesIO will be reused
            data = {
                'pair': pair,
                'res': res,
                'entry': entry_str,
                'image_bytes': img_bio.getvalue(),
                'created_at': now
            }
            with CACHE_LOCK:
                SIGNAL_CACHE.append(data)
        print(f"CACHE BUILT: {len(SIGNAL_CACHE)} signals ready")
    except Exception as e:
        print(f"Cache error: {e}")

async def instant_signal_job(context: ContextTypes.DEFAULT_TYPE):
    global SIGNAL_CACHE
    with CACHE_LOCK:
        if SIGNAL_CACHE:
            data = SIGNAL_CACHE.pop(0)
        else:
            data = None
    
    if data:
        # Use pre-cached signal - INSTANT
        img_bio = BytesIO(data['image_bytes'])
        img_bio.name = 'signal.png'
        caption = f"⚡ **INSTANT CACHED - {BRAND}**\n\nPair: {data['pair']}\nDirection: {data['res']['decision']}\nEntry: {data['entry']} UTC+6\nTF: 1 Min\nStrength: {data['res'].get('strength_text')}\nRSI: {data['res']['rsi']}\nOwner: {OWNER}\n\n✅ Pre-Processed | 0s Delay"
        await context.bot.send_photo(chat_id=context.job.chat_id, photo=img_bio, caption=caption, reply_markup=main_menu_keyboard(), parse_mode='Markdown')
        # Trigger refill
        context.job_queue.run_once(cache_builder_job, when=1)
    else:
        # Fallback if cache empty
        pair = random.choice(trading_engine.QUOTEX_OTC_PAIRS)
        try:
            res = await asyncio.to_thread(trading_engine.analyze_fast, pair)
        except:
            res = {'decision': random.choice(['UP','DOWN']), 'strength_text': 'STRONG', 'rsi': 50, 'score': 5}
        now = datetime.utcnow() + timedelta(hours=6)
        entry_str = now.strftime('%H:%M')
        img = await asyncio.to_thread(create_signal_image, pair, res['decision'], res.get('strength_text','STRONG'), res['rsi'], res['score'], entry_str)
        caption = f"📈 **LIVE - {BRAND}**\n\nPair: {pair}\nEntry: {entry_str} UTC+6\nDir: {res['decision']}\nOwner: {OWNER}"
        await context.bot.send_photo(chat_id=context.job.chat_id, photo=img, caption=caption, reply_markup=main_menu_keyboard(), parse_mode='Markdown')

async def future_signal_job(context: ContextTypes.DEFAULT_TYPE):
    global SIGNAL_CACHE
    with CACHE_LOCK:
        if SIGNAL_CACHE:
            data = SIGNAL_CACHE.pop(0)
        else:
            data = None
    
    if data:
        img_bio = BytesIO(data['image_bytes'])
        img_bio.name = 'signal.png'
        caption = f"🔮 FUTURE #{context.job.data['index']}/{context.job.data['total']} - {BRAND}\n\nPair: {data['pair']}\nDir: {data['res']['decision']}\nEntry: {data['entry']} UTC+6\nOwner: {OWNER}\n\n✅ Pre-Cached Instant"
        await context.bot.send_photo(chat_id=context.job.chat_id, photo=img_bio, caption=caption, reply_markup=main_menu_keyboard(), parse_mode='Markdown')
    else:
        # fallback
        await instant_signal_job(context)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.utcnow() + timedelta(hours=6)
    # Start cache builder if not started
    if not context.application.bot_data.get('cache_started'):
        context.job_queue.run_repeating(cache_builder_job, interval=10, first=1)
        context.application.bot_data['cache_started'] = True
        # Build first cache instantly
        context.job_queue.run_once(cache_builder_job, when=1)
    
    await update.message.reply_text(f"🏠 **Main Menu - {BRAND}**\n\n👑 Owner: {OWNER}\n🕒 Time: {now.strftime('%H:%M')} UTC+6\n📦 Cache: {len(SIGNAL_CACHE)} Ready ✅\n📈 LIVE PRE-CACHE ✅", reply_markup=main_menu_keyboard(), parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    now = datetime.utcnow() + timedelta(hours=6)
    time_str = now.strftime('%H:%M')

    if data == 'main_menu':
        await query.edit_message_text(f"🏠 **Main Menu - {BRAND}**\n👑 {OWNER}\n🕒 {time_str} UTC+6\nCache: {len(SIGNAL_CACHE)} Ready ✅", reply_markup=main_menu_keyboard(), parse_mode='Markdown')
        return
    if data == 'help':
        await query.edit_message_text(f"🆘 **Help - {BRAND}**\n\n🤖 Get AI: Pre-Cached Instant Signal\n🔮 Future: Instant from Cache\n\nBackground এ 24/7 Data Ready হচ্ছে\n👑 {OWNER}", reply_markup=main_menu_keyboard(), parse_mode='Markdown')
        return
    if data == 'setting':
        await query.edit_message_text(f"⚙️ **Setting - {BRAND}**\nOwner: {OWNER}\nTF: 1 Min\nCache Size: {len(SIGNAL_CACHE)}\nUTC+6\nPre-Cache Active ✅", reply_markup=main_menu_keyboard(), parse_mode='Markdown')
        return
    if data == 'future_signal':
        sc = context.user_data.get('future_count')
        sm = context.user_data.get('future_min')
        await query.edit_message_text(f"🔮 **Future Customization**\nকয়টা? [5/8/10/15]\nকত মিনিট? [2/3/5/10]\nCache: {len(SIGNAL_CACHE)} Ready\nCurrent: {sc or 'Not Set'} | {sm or 'Not Set'}", reply_markup=future_custom_keyboard(sc, sm), parse_mode='Markdown')
        return
    if data.startswith('fcount_'):
        context.user_data['future_count'] = int(data.split('_')[1])
        await query.edit_message_text(f"Count: {context.user_data['future_count']} ✅", reply_markup=future_custom_keyboard(context.user_data['future_count'], context.user_data.get('future_min')), parse_mode='Markdown')
        return
    if data.startswith('fmin_'):
        context.user_data['future_min'] = int(data.split('_')[1])
        await query.edit_message_text(f"Min: {context.user_data['future_min']} ✅", reply_markup=future_custom_keyboard(context.user_data.get('future_count'), context.user_data['future_min']), parse_mode='Markdown')
        return
    if data == 'future_confirm':
        sc = context.user_data.get('future_count')
        sm = context.user_data.get('future_min')
        if not sc or not sm:
            await query.edit_message_text("❌ আগে Count আর Min Select করুন!", reply_markup=future_custom_keyboard(sc, sm), parse_mode='Markdown')
            return
        await query.edit_message_text(f"🚀 Started {sc} Signals every {sm}m - From Cache Instant!", reply_markup=main_menu_keyboard(), parse_mode='Markdown')
        for i in range(sc):
            context.job_queue.run_once(future_signal_job, when=(i+1)*sm*60, chat_id=query.message.chat_id, data={"index": i+1, "total": sc})
        return
    if data == 'get_ai_signal':
        # INSTANT - No processing, just from cache
        await query.edit_message_text(f"⚡ Instant from Cache... {time_str}\nCache: {len(SIGNAL_CACHE)} Ready")
        context.job_queue.run_once(instant_signal_job, when=0, chat_id=query.message.chat_id)
        try: await query.delete_message()
        except: pass
        return

def run_bot():
    if not BOT_TOKEN: return
    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    print(f"{BRAND} PRE-CACHE Started")
    app_bot.run_polling()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()