import os, csv, io, sqlite3, logging, threading, math
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, jsonify
from werkzeug.serving import make_server
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

NAME = "FINOREX PREMIUM BOT"
TZ = ZoneInfo("Asia/Dhaka")
TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "finorex.db")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(NAME)
web = Flask(__name__)

@web.get("/")
def home():
    return jsonify(name=NAME, status="running", mode="CSV analysis only")

@web.get("/health")
def health():
    return jsonify(status="ok"), 200

def db():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.execute("""CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, pair TEXT,
        direction TEXT, score INTEGER, payout INTEGER, created_at TEXT)""")
    return con

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 GET AI SIGNAL", callback_data="signal")],
        [InlineKeyboardButton("🔮 FUTURE AI SIGNAL", callback_data="future")],
        [InlineKeyboardButton("📸 LIVE CHART SCANNER", callback_data="scanner")],
        [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")],
        [InlineKeyboardButton("🆘 HELP", callback_data="help")]])

def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Signal History", callback_data="history")],
        [InlineKeyboardButton("⬅️ Main Menu", callback_data="home")]])

def read_csv(data):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must use UTF-8 encoding.") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV header missing.")
    headers = {str(x).strip().lower() for x in reader.fieldnames if x}
    if not {"open", "high", "low", "close"}.issubset(headers):
        raise ValueError("Required columns: open,high,low,close")
    candles = []
    for number, row in enumerate(reader, start=2):
        r = {str(k).strip().lower(): v for k, v in row.items() if k}
        try:
            c = {k: float(r[k]) for k in ("open", "high", "low", "close")}
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Invalid/missing OHLC value at CSV row {number}.")
        if not all(math.isfinite(v) and v > 0 for v in c.values()):
            raise ValueError(f"Non-positive or non-finite price at row {number}.")
        if c["low"] > min(c["open"], c["close"]) or c["high"] < max(c["open"], c["close"]) or c["low"] > c["high"]:
            raise ValueError(f"Invalid OHLC range at row {number}.")
        candles.append(c)
    if len(candles) < 35:
        raise ValueError("At least 35 complete candles are required for these indicators.")
    return candles

def sma(values, period):
    if len(values) < period:
        raise ValueError("Not enough data for SMA.")
    return sum(values[-period:]) / period

def ema_series(values, period):
    if len(values) < period:
        raise ValueError("Not enough data for EMA.")
    alpha = 2 / (period + 1)
    value = sum(values[:period]) / period
    out = [None] * (period - 1) + [value]
    for x in values[period:]:
        value = alpha * x + (1 - alpha) * value
        out.append(value)
    return out

def rsi_wilder(values, period=14):
    changes = [values[i] - values[i-1] for i in range(1, len(values))]
    gains = [max(x, 0) for x in changes]
    losses = [max(-x, 0) for x in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100 - (100 / (1 + avg_gain / avg_loss))

def analyze(candles, payout):
    if not isinstance(payout, int) or not 80 <= payout <= 100:
        return None, "Payout must be verified on Quotex and be at least 80%."
    close = [c["close"] for c in candles]
    high = [c["high"] for c in candles]
    low = [c["low"] for c in candles]
    e9s, e21s = ema_series(close, 9), ema_series(close, 21)
    e9, e21 = e9s[-1], e21s[-1]
    sma20 = sma(close, 20)
    rsi = rsi_wilder(close, 14)

    # MACD(12,26,9), calculated from EMA series.
    e12s, e26s = ema_series(close, 12), ema_series(close, 26)
    macd_line = [a-b if a is not None and b is not None else None for a,b in zip(e12s,e26s)]
    valid_macd = [x for x in macd_line if x is not None]
    signal_line = ema_series(valid_macd, 9)
    macd_now, macd_signal = valid_macd[-1], signal_line[-1]

    # Bollinger Bands(20,2 population standard deviation).
    window = close[-20:]
    mean = sum(window) / 20
    sd = math.sqrt(sum((x-mean)**2 for x in window) / 20)
    upper, lower = mean + 2*sd, mean - 2*sd

    candle_ranges = [h-l for h,l in zip(high,low)]
    baseline = sum(candle_ranges[-20:]) / 20
    if baseline <= 0:
        return None, "Insufficient candle movement."
    if candle_ranges[-1] > baseline * 2.5:
        return None, "High volatility candle. WAIT / NO-TRADE."

    checks_up = [
        e9 > e21, close[-1] > sma20, 50 < rsi < 68,
        macd_now > macd_signal, close[-1] > mean and close[-1] < upper
    ]
    checks_down = [
        e9 < e21, close[-1] < sma20, 32 < rsi < 50,
        macd_now < macd_signal, close[-1] < mean and close[-1] > lower
    ]
    up_score, down_score = sum(checks_up), sum(checks_down)
    # Require broad agreement; do not force a direction when indicators conflict.
    if up_score >= 4 and up_score > down_score:
        direction, score = "UP", up_score
    elif down_score >= 4 and down_score > up_score:
        direction, score = "DOWN", down_score
    else:
        return None, "Indicators are not sufficiently aligned. WAIT / NO-TRADE."

    return {
        "direction": direction, "score": score, "rsi": round(rsi, 2),
        "ema9": round(e9, 8), "ema21": round(e21, 8),
        "sma20": round(sma20, 8), "macd": round(macd_now, 8),
        "macd_signal": round(macd_signal, 8),
        "bb_upper": round(upper, 8), "bb_middle": round(mean, 8),
        "bb_lower": round(lower, 8)
    }, None

def save(user, pair, result, payout):
    with db() as con:
        cur = con.execute(
            "INSERT INTO signals(user_id,pair,direction,score,payout,created_at) VALUES(?,?,?,?,?,?)",
            (user, pair, result["direction"], result["score"], payout, datetime.now(TZ).isoformat()))
        return cur.lastrowid

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 {NAME}\nQuotex OTC chart-data analysis.\nUpload an OHLC CSV to check a setup.\nTimezone: Asia/Dhaka (BST).",
        reply_markup=main_menu())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d == "home":
        await q.message.reply_text(NAME, reply_markup=main_menu())
    elif d == "signal":
        await q.message.reply_text("Upload CSV with open,high,low,close columns and at least 35 candles. Filename: PAIR_OTC_85.csv. Enter the actual Quotex payout; it is not verified automatically.")
    elif d == "future":
        await q.message.reply_text("Future prices cannot be known in advance. This bot will not fabricate future UP/DOWN signals. Upload current candle data for a current setup check.")
    elif d == "scanner":
        await q.message.reply_text("Screenshot received by this bot can be stored, but image-to-OHLC extraction and automatic Quotex screen scanning are not implemented yet. Upload matching CSV for analysis.")
    elif d == "settings":
        await q.message.reply_text("⚙️ SETTINGS\nMarket: Quotex OTC only\nMinimum declared payout: 80%\nTimezone: Asia/Dhaka\nIndicators: EMA 9/21, SMA 20, RSI 14, MACD 12/26/9, Bollinger Bands 20/2\nNo-trade filter: ON", reply_markup=settings_menu())
    elif d == "history":
        with db() as con:
            rows = con.execute("SELECT pair,direction,payout,created_at FROM signals WHERE user_id=? ORDER BY id DESC LIMIT 10", (q.from_user.id,)).fetchall()
        if rows:
            msg = "📚 RECENT ANALYSES\n" + "\n".join(
                f"{p} | {di} | {po}% | {datetime.fromisoformat(t).strftime('%d-%b %I:%M %p')} BST"
                for p,di,po,t in rows)
        else:
            msg = "📚 No saved analyses yet."
        await q.message.reply_text(msg, reply_markup=settings_menu())
    elif d == "help":
        await q.message.reply_text("1) Export Quotex OTC candles as CSV.\n2) Required columns: open,high,low,close.\n3) Minimum 35 rows.\n4) Filename: EURUSD_OTC_85.csv.\n5) Upload it.\nThis version analyzes supplied data only; it does not connect to Quotex or fetch live prices.")

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Screenshot received. Automatic verified OHLC extraction is not active yet. I will not guess candle prices or payout. Please upload matching OHLC CSV data.")

async def document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".csv"):
        await update.message.reply_text("Please upload a .csv file.")
        return
    try:
        parts = doc.file_name.rsplit(".", 1)[0].split("_")
        if len(parts) < 3 or parts[-2].upper() != "OTC":
            raise ValueError("Filename format: EURUSD_OTC_85.csv")
        pair = "_".join(parts[:-2]).upper() + "_OTC"
        if not pair.replace("_OTC", "").replace("_", "").isalnum():
            raise ValueError("Invalid pair name in filename.")
        payout_text = parts[-1].replace("%", "")
        if not payout_text.isdigit():
            raise ValueError("Filename must end with the actual payout, e.g. _85.csv")
        payout = int(payout_text)
        f = await doc.get_file()
        data = bytes(await f.download_as_bytearray())
        candles = read_csv(data)
        result, reason = analyze(candles, payout)
        if reason:
            await update.message.reply_text(f"🛡️ RISK FILTER: REJECTED\n{pair}\n{reason}")
            return
        sid = save(update.effective_user.id, pair, result, payout)
        now = datetime.now(TZ).strftime("%d-%b-%Y %I:%M:%S %p")
        arrow = "🟢 UP" if result["direction"] == "UP" else "🔴 DOWN"
        msg = (
            f"🤖 {NAME}\n\nPair: {pair}\nDirection: {arrow}\n"
            f"Analysis Score: {result['score']}/5 (indicator alignment, not win probability)\n"
            f"RSI 14: {result['rsi']}\nEMA 9/21: {result['ema9']} / {result['ema21']}\n"
            f"SMA 20: {result['sma20']}\nMACD / Signal: {result['macd']} / {result['macd_signal']}\n"
            f"BB Upper/Middle/Lower: {result['bb_upper']} / {result['bb_middle']} / {result['bb_lower']}\n"
            f"Declared payout: {payout}% (not independently verified)\n"
            f"Analysis time: {now} BST\nRisk checks: basic CSV checks passed\n"
            f"Analysis ID: FX-{sid:06d}\n\n"
            "ONE STEP MTG: optional single recovery step only. No guaranteed recovery or profit. Demo-test first."
        )
        await update.message.reply_text(msg)
    except Exception as exc:
        log.exception("CSV analysis failed")
        await update.message.reply_text(f"Could not analyze file: {exc}")

async def errors(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Telegram error", exc_info=context.error)

def run():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN missing. Set it in Render Environment Variables.")
    port = int(os.getenv("PORT", "10000"))
    server = make_server("0.0.0.0", port, web)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    bot = Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CallbackQueryHandler(buttons))
    bot.add_handler(MessageHandler(filters.PHOTO, photo))
    bot.add_handler(MessageHandler(filters.Document.ALL, document))
    bot.add_error_handler(errors)
    log.info("%s starting on port %s", NAME, port)
    bot.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    run()
