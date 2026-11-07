import os, csv, io, sqlite3, logging, threading
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, jsonify
from werkzeug.serving import make_server
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

NAME = 'FINOREX PREMIUM BOT'
TZ = ZoneInfo('Asia/Dhaka')
TOKEN = os.getenv('BOT_TOKEN', '')
DB_PATH = os.getenv('DB_PATH', 'finorex.db')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(NAME)
web = Flask(__name__)

@web.get('/')
def home(): return jsonify(name=NAME, status='running')

@web.get('/health')
def health(): return jsonify(status='ok'), 200

def db():
    con = sqlite3.connect(DB_PATH)
    con.execute('''CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, pair TEXT,
        direction TEXT, score INTEGER, payout INTEGER, created_at TEXT)''')
    return con

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🎯 GET AI SIGNAL', callback_data='signal')],
        [InlineKeyboardButton('🔮 FUTURE AI SIGNAL', callback_data='future')],
        [InlineKeyboardButton('📸 LIVE CHART SCANNER', callback_data='scanner')],
        [InlineKeyboardButton('⚙️ SETTINGS', callback_data='settings')],
        [InlineKeyboardButton('🆘 HELP', callback_data='help')]])

def settings_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton('📚 Signal History', callback_data='history')],
                                 [InlineKeyboardButton('⬅️ Main Menu', callback_data='home')]])

def read_csv(data):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
    if not reader.fieldnames: raise ValueError('CSV header missing.')
    if not {'open','high','low','close'}.issubset({x.strip().lower() for x in reader.fieldnames}):
        raise ValueError('CSV columns must be: open,high,low,close')
    candles=[]
    for row in reader:
        r={k.strip().lower():v for k,v in row.items() if k}
        c={k:float(r[k]) for k in ('open','high','low','close')}
        if c['low'] > min(c['open'],c['close']) or c['high'] < max(c['open'],c['close']) or c['low']>c['high']:
            raise ValueError('Invalid OHLC candle values.')
        candles.append(c)
    if len(candles)<30: raise ValueError('At least 30 candles are required.')
    return candles

def ema(values, period):
    a=2/(period+1); value=sum(values[:period])/period
    for x in values[period:]: value=a*x+(1-a)*value
    return value

def analyze(candles,payout):
    if not 80<=payout<=100: return None,'Payout below 80% or invalid.'
    close=[c['close'] for c in candles]; high=[c['high'] for c in candles]; low=[c['low'] for c in candles]
    if any(x<=0 for x in close): return None,'Invalid price data.'
    e9,e21=ema(close,9),ema(close,21)
    changes=[close[i]-close[i-1] for i in range(1,len(close))][-14:]
    gain=sum(max(x,0) for x in changes)/14; loss=sum(max(-x,0) for x in changes)/14
    rsi=100.0 if loss==0 and gain>0 else (50.0 if loss==0 else 100-(100/(1+gain/loss)))
    ranges=[h-l for h,l in zip(high,low)]; baseline=sum(ranges[-20:])/20
    if baseline<=0: return None,'Insufficient candle movement.'
    if ranges[-1]>baseline*2.5: return None,'High volatility. WAIT / NO-TRADE.'
    up=(e9>e21 and close[-1]>e9 and 50<rsi<68)
    down=(e9<e21 and close[-1]<e9 and 32<rsi<50)
    if up: direction='UP'
    elif down: direction='DOWN'
    else: return None,'No aligned setup. WAIT / NO-TRADE.'
    return {'direction':direction,'score':3,'rsi':round(rsi,1),'ema9':round(e9,6),'ema21':round(e21,6)},None

def save(user,pair,result,payout):
    with db() as con:
        cur=con.execute('INSERT INTO signals(user_id,pair,direction,score,payout,created_at) VALUES(?,?,?,?,?,?)',
          (user,pair,result['direction'],result['score'],payout,datetime.now(TZ).isoformat()))
        return cur.lastrowid

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f'🤖 {NAME}\nQuotex OTC analysis assistant.\nUpload an OHLC CSV to check a setup.\nTimezone: Bangladesh (BST)',reply_markup=main_menu())

async def buttons(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); d=q.data
    if d=='home': await q.message.reply_text(NAME,reply_markup=main_menu())
    elif d=='signal': await q.message.reply_text('Send CSV with open,high,low,close columns (30+ candles). Filename example: EURUSD_OTC_85.csv. 85 must be the actual payout shown by Quotex.')
    elif d=='future': await q.message.reply_text('Future market prices cannot be known in advance. I will not invent future UP/DOWN signals. Upload current candles for a current setup check.')
    elif d=='scanner': await q.message.reply_text('Send a chart screenshot here. This starter receives the image but does not yet extract verified OHLC from pixels. Send the matching CSV for analysis.')
    elif d=='settings': await q.message.reply_text('⚙️ SETTINGS\nMarket: Quotex OTC only\nMinimum payout: 80%\nTimezone: Asia/Dhaka\nFilters: EMA 9/21 + RSI + candle-range volatility\nNo-trade filter: ON',reply_markup=settings_menu())
    elif d=='history':
        with db() as con: rows=con.execute('SELECT pair,direction,payout,created_at FROM signals WHERE user_id=? ORDER BY id DESC LIMIT 10',(q.from_user.id,)).fetchall()
        msg='📚 RECENT ANALYSES\n'+'\n'.join(f'{p} | {di} | {po}% | {datetime.fromisoformat(t).strftime("%d-%b %I:%M %p")} BST' for p,di,po,t in rows) if rows else '📚 No saved analyses yet.'
        await q.message.reply_text(msg,reply_markup=settings_menu())
    elif d=='help': await q.message.reply_text('1) Export candle data as CSV.\n2) Columns: open,high,low,close.\n3) Minimum 30 rows.\n4) Filename: EURUSD_OTC_85.csv.\n5) Upload it.\nThis version does not connect to Quotex or fetch live prices automatically.')

async def photo(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('📸 Screenshot received. Automatic image-to-candle extraction is not enabled yet; exact candle prices/payout must not be guessed. Please send matching OHLC CSV data.')

async def document(update:Update,context:ContextTypes.DEFAULT_TYPE):
    doc=update.message.document
    if not doc.file_name.lower().endswith('.csv'):
        await update.message.reply_text('Please upload a .csv file.'); return
    try:
        parts=doc.file_name.rsplit('.',1)[0].split('_')
        if len(parts)<3 or parts[-2].upper()!='OTC': raise ValueError('Filename format: EURUSD_OTC_85.csv')
        pair='_'.join(parts[:-2]).upper()+'_OTC'; payout=int(parts[-1].replace('%',''))
        f=await doc.get_file(); data=bytes(await f.download_as_bytearray())
        candles=read_csv(data); result,reason=analyze(candles,payout)
        if reason:
            await update.message.reply_text(f'🛡️ RISK FILTER: REJECTED\n{pair}\n{reason}'); return
        sid=save(update.effective_user.id,pair,result,payout); now=datetime.now(TZ).strftime('%d-%b-%Y %I:%M:%S %p')
        arrow='🟢 UP' if result['direction']=='UP' else '🔴 DOWN'
        await update.message.reply_text(f'🤖 {NAME}\n\nPair: {pair}\nDirection: {arrow}\nAnalysis Score: {result["score"]}/3\nRSI: {result["rsi"]}\nEMA 9: {result["ema9"]}\nEMA 21: {result["ema21"]}\nPayout: {payout}%\nAnalysis time: {now} BST\nRisk checks: PASSED (basic only)\nSignal ID: FX-{sid:06d}\n\nONE STEP MTG: optional single recovery step only; no guaranteed recovery or profit. Demo-test first.')
    except Exception as e:
        log.exception('CSV analysis failed'); await update.message.reply_text(f'Could not analyze file: {e}')

async def errors(update:object,context:ContextTypes.DEFAULT_TYPE): log.error('Telegram error',exc_info=context.error)

def run():
    if not TOKEN: raise RuntimeError('BOT_TOKEN missing. Set it in Render Environment Variables.')
    port=int(os.getenv('PORT','10000')); server=make_server('0.0.0.0',port,web)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    bot=Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler('start',start)); bot.add_handler(CallbackQueryHandler(buttons))
    bot.add_handler(MessageHandler(filters.PHOTO,photo)); bot.add_handler(MessageHandler(filters.Document.ALL,document))
    bot.add_error_handler(errors)
    log.info('%s starting on port %s',NAME,port); bot.run_polling(drop_pending_updates=True)

if __name__=='__main__': run()
