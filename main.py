import os
import json
import math
import time
import sqlite3
import logging
import threading
import asyncio
from datetime import datetime, timezone
from typing import Optional

from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# FINOREX PREMIUM BOT
# Quotex OTC chart-data analysis backend
# =========================================================

APP_NAME = "FINOREX PREMIUM BOT"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
SCANNER_TOKEN = os.getenv("SCANNER_TOKEN", "").strip()
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "").strip()

ADMIN_IDS = set()
for item in ADMIN_IDS_RAW.split(","):
    item = item.strip()
    if item.isdigit():
        ADMIN_IDS.add(int(item))

PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "finorex_history.db")

MIN_PAYOUT = 80.0
MIN_CANDLES = 35
MAX_CANDLES = 500
MAX_VOLATILITY_PERCENT = 0.80

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(APP_NAME)

app = Flask(__name__)
bot_application = None
bot_loop = None

# Latest accepted data, indexed by pair and timeframe.
latest_market_data = {}
market_lock = threading.Lock()


# =========================================================
# DATABASE
# =========================================================

def db_connect():
    connection = sqlite3.connect(DB_PATH, timeout=20)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    with db_connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT UNIQUE NOT NULL,
                pair TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                direction TEXT NOT NULL,
                payout REAL NOT NULL,
                score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING'
            )
        """)
        db.commit()


def save_signal(signal):
    with db_connect() as db:
        db.execute("""
            INSERT OR IGNORE INTO signal_history
            (signal_id, pair, timeframe, direction, payout,
             score, risk_level, reason, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
        """, (
            signal["signal_id"],
            signal["pair"],
            signal["timeframe"],
            signal["direction"],
            signal["payout"],
            signal["score"],
            signal["risk_level"],
            signal["reason"],
            signal["created_at"],
        ))
        db.commit()


def get_recent_signals(limit=10):
    with db_connect() as db:
        rows = db.execute("""
            SELECT * FROM signal_history
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]


# =========================================================
# VALIDATION AND INDICATORS
# =========================================================

def number(value):
    try:
        result = float(value)
        if math.isfinite(result):
            return result
    except (TypeError, ValueError):
        pass
    return None


def validate_market_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")

    pair = str(payload.get("pair", "")).strip()
    market = str(payload.get("market", "")).strip().upper()
    timeframe = str(payload.get("timeframe", "")).strip().lower()
    payout = number(payload.get("payout"))
    candles = payload.get("candles")

    if not pair:
        raise ValueError("pair is required.")

    if market != "OTC":
        raise ValueError("Only OTC market data is accepted.")

    if not timeframe:
        raise ValueError("timeframe is required.")

    if payout is None or payout < 0 or payout > 100:
        raise ValueError("A valid payout percentage is required.")

    if not isinstance(candles, list):
        raise ValueError("candles must be a list.")

    if len(candles) < MIN_CANDLES:
        raise ValueError(
            f"At least {MIN_CANDLES} candles are required."
        )

    if len(candles) > MAX_CANDLES:
        raise ValueError(f"Maximum {MAX_CANDLES} candles are allowed.")

    clean_candles = []

    for candle in candles:
        if not isinstance(candle, dict):
            raise ValueError("Invalid candle format.")

        open_price = number(candle.get("open"))
        high_price = number(candle.get("high"))
        low_price = number(candle.get("low"))
        close_price = number(candle.get("close"))
        timestamp = number(candle.get("timestamp"))

        values = [open_price, high_price, low_price, close_price]

        if any(value is None or value <= 0 for value in values):
            raise ValueError("Candle prices must be positive numbers.")

        if high_price < max(open_price, close_price, low_price):
            raise ValueError("Invalid candle high value.")

        if low_price > min(open_price, close_price, high_price):
            raise ValueError("Invalid candle low value.")

        clean_candles.append({
            "timestamp": timestamp,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
        })

    clean_candles.sort(
        key=lambda item: (
            item["timestamp"]
            if item["timestamp"] is not None
            else 0
        )
    )

    return {
        "pair": pair,
        "market": market,
        "timeframe": timeframe,
        "payout": payout,
        "candles": clean_candles,
    }


def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values, period):
    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)
    result = sum(values[:period]) / period

    for value in values[period:]:
        result = (value * multiplier) + (
            result * (1 - multiplier)
        )

    return result


def calculate_rsi(values, period=14):
    if len(values) <= period:
        return None

    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    gains = [max(change, 0) for change in changes]
    losses = [abs(min(change, 0)) for change in changes]

    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        average_gain = (
            (average_gain * (period - 1)) + gains[i]
        ) / period

        average_loss = (
            (average_loss * (period - 1)) + losses[i]
        ) / period

    if average_loss == 0:
        return 100.0

    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def calculate_macd(values):
    if len(values) < 35:
        return None, None

    fast = ema(values, 12)
    slow = ema(values, 26)

    if fast is None or slow is None:
        return None, None

    macd_line = fast - slow

    # Signal-line approximation from available recent series.
    macd_series = []
    for end in range(26, len(values) + 1):
        section = values[:end]
        fast_value = ema(section, 12)
        slow_value = ema(section, 26)

        if fast_value is not None and slow_value is not None:
            macd_series.append(fast_value - slow_value)

    signal_line = ema(macd_series, 9)

    return macd_line, signal_line


def calculate_bollinger(values, period=20):
    if len(values) < period:
        return None, None, None

    window = values[-period:]
    middle = sum(window) / period

    variance = sum(
        (value - middle) ** 2 for value in window
    ) / period

    deviation = math.sqrt(variance)

    return (
        middle + (2 * deviation),
        middle,
        middle - (2 * deviation),
    )


def calculate_volatility(candles):
    recent = candles[-20:]
    ranges = []

    for candle in recent:
        close_price = candle["close"]
        if close_price > 0:
            ranges.append(
                (candle["high"] - candle["low"])
                / close_price * 100
            )

    if not ranges:
        return None

    return sum(ranges) / len(ranges)


# =========================================================
# ANALYSIS ENGINE AND RISK FILTER
# =========================================================

def analyze_market(data):
    candles = data["candles"]
    closes = [item["close"] for item in candles]

    current_price = closes[-1]

    ma = sma(closes, 9)
    sma_value = sma(closes, 20)
    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    rsi = calculate_rsi(closes)
    macd, macd_signal = calculate_macd(closes)
    upper, middle, lower = calculate_bollinger(closes)
    volatility = calculate_volatility(candles)

    indicators = {
        "MA9": ma,
        "SMA20": sma_value,
        "EMA9": ema9,
        "EMA21": ema21,
        "RSI14": rsi,
        "MACD": macd,
        "MACD_SIGNAL": macd_signal,
        "BB_UPPER": upper,
        "BB_MIDDLE": middle,
        "BB_LOWER": lower,
        "VOLATILITY_PERCENT": volatility,
    }

    if any(value is None for value in indicators.values()):
        return {
            "valid": False,
            "direction": "WAIT",
            "reason": "Indicator data is incomplete.",
            "indicators": indicators,
        }

    # Reject payout below 80%.
    if data["payout"] < MIN_PAYOUT:
        return {
            "valid": False,
            "direction": "WAIT",
            "reason": "Payout is below the 80% minimum.",
            "indicators": indicators,
        }

    # Reject unusually high candle volatility.
    if volatility > MAX_VOLATILITY_PERCENT:
        return {
            "valid": False,
            "direction": "WAIT",
            "reason": "Volatility exceeds the configured risk limit.",
            "indicators": indicators,
        }

    bullish = 0
    bearish = 0

    if ema9 > ema21:
        bullish += 1
    elif ema9 < ema21:
        bearish += 1

    if current_price > sma_value:
        bullish += 1
    elif current_price < sma_value:
        bearish += 1

    if ma > sma_value:
        bullish += 1
    elif ma < sma_value:
        bearish += 1

    if macd > macd_signal:
        bullish += 1
    elif macd < macd_signal:
        bearish += 1

    if 50 < rsi < 70:
        bullish += 1
    elif 30 < rsi < 50:
        bearish += 1

    # Bollinger confirmation: price relative to middle band.
    if current_price > middle:
        bullish += 1
    elif current_price < middle:
        bearish += 1

    score = max(bullish, bearish)

    if bullish >= 5 and bullish - bearish >= 3:
        direction = "UP"
    elif bearish >= 5 and bearish - bullish >= 3:
        direction = "DOWN"
    else:
        direction = "WAIT"

    if direction == "WAIT":
        return {
            "valid": False,
            "direction": "WAIT",
            "reason": "Indicators do not show sufficient agreement.",
            "score": score,
            "indicators": indicators,
        }

    return {
        "valid": True,
        "direction": direction,
        "reason": (
            "Technical indicators show aligned directional evidence."
        ),
        "score": score,
        "risk_level": "HIGH" if volatility > 0.50 else "MODERATE",
        "indicators": indicators,
    }


# =========================================================
# SIGNAL CREATION
# =========================================================

def create_signal(data):
    analysis = analyze_market(data)

    if not analysis.get("valid"):
        return None, analysis

    now = datetime.now(timezone.utc)
    signal_id = now.strftime("%Y%m%d%H%M%S%f")

    signal = {
        "signal_id": signal_id,
        "pair": data["pair"],
        "timeframe": data["timeframe"],
        "direction": analysis["direction"],
        "payout": data["payout"],
        "score": analysis["score"],
        "risk_level": analysis["risk_level"],
        "reason": analysis["reason"],
        "created_at": now.isoformat(),
    }

    save_signal(signal)
    return signal, analysis


def format_signal(signal):
    return (
        f"🎯 {APP_NAME}\n\n"
        f"Pair: {signal['pair']}\n"
        f"Market: QUOTEX OTC\n"
        f"Direction: {signal['direction']}\n"
        f"Timeframe: {signal['timeframe']}\n"
        f"Payout: {signal['payout']:.0f}%\n"
        f"Analysis Score: {signal['score']}/6\n"
        f"Risk Level: {signal['risk_level']}\n"
        f"Signal ID: {signal['signal_id']}\n\n"
        f"Reason: {signal['reason']}\n\n"
        f"⚠️ Analysis only. No profit is guaranteed.\n"
        f"ONE STEP MTG MUST BE — optional, not guaranteed recovery."
    )


# =========================================================
# SCANNER API
# =========================================================

@app.get("/")
def home():
    return jsonify({
        "name": APP_NAME,
        "status": "running",
        "market": "Quotex OTC only",
    })


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": APP_NAME,
        "time": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.post("/scanner/submit")
def scanner_submit():
    if not SCANNER_TOKEN:
        return jsonify({
            "error": "SCANNER_TOKEN is not configured."
        }), 503

    supplied_token = request.headers.get(
        "X-Scanner-Token", ""
    ).strip()

    if supplied_token != SCANNER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = validate_market_payload(request.get_json(silent=True))

        key = (data["pair"], data["timeframe"])

        with market_lock:
            latest_market_data[key] = data

        signal, analysis = create_signal(data)

        if signal:
            send_signal_to_admins(signal)

            return jsonify({
                "accepted": True,
                "signal_created": True,
                "signal": signal,
            }), 200

        return jsonify({
            "accepted": True,
            "signal_created": False,
            "decision": "WAIT",
            "reason": analysis.get("reason"),
            "indicators": analysis.get("indicators"),
        }), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("Scanner submission failed")
        return jsonify({"error": "Internal server error"}), 500


# =========================================================
# TELEGRAM BOT
# =========================================================

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "🎯 GET AI SIGNAL",
                callback_data="get_signal",
            )
        ],
        [
            InlineKeyboardButton(
                "🔮 FUTURE AI SIGNAL",
                callback_data="future_signal",
            )
        ],
        [
            InlineKeyboardButton(
                "📸 LIVE CHART SCANNER",
                callback_data="chart_scanner",
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ SETTINGS",
                callback_data="settings",
            )
        ],
        [
            InlineKeyboardButton(
                "🆘 HELP",
                callback_data="help",
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        f"Welcome to {APP_NAME}!\n\n"
        "Quotex OTC chart analysis system.\n"
        "Choose an option:",
        reply_markup=main_menu(),
    )


async def menu_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    if query.data == "get_signal":
        recent = get_recent_signals(1)

        if not recent:
            await query.message.reply_text(
                "WAIT — No verified signal is available yet."
            )
        else:
            signal = recent[0]
            await query.message.reply_text(
                format_signal(signal)
            )

    elif query.data == "future_signal":
        await query.message.reply_text(
            "🔮 FUTURE AI SIGNAL\n\n"
            "A future direction cannot be guaranteed. "
            "The bot will only show a signal when fresh chart "
            "data passes the technical and risk checks.\n\n"
            "Current status: WAIT until valid data arrives."
        )

    elif query.data == "chart_scanner":
        await query.message.reply_text(
            "📸 LIVE CHART SCANNER\n\n"
            "Send chart data through the authenticated "
            "Scanner API endpoint:\n"
            "/scanner/submit\n\n"
            "A chart photo alone is not treated as verified "
            "OHLC market data."
        )

    elif query.data == "settings":
        await query.message.reply_text(
            "⚙️ SETTINGS\n\n"
            f"Minimum payout: {MIN_PAYOUT:.0f}%\n"
            f"Minimum candles: {MIN_CANDLES}\n"
            "Market: Quotex OTC only\n"
            "Automatic strategy selection: Enabled"
        )

    elif query.data == "help":
        await query.message.reply_text(
            "🆘 HELP\n\n"
            "1. Connect a permitted Windows or Android Scanner.\n"
            "2. Submit real OTC OHLC candle data.\n"
            "3. The backend checks indicators and risk.\n"
            "4. If the setup is weak, the decision is WAIT.\n\n"
            "This bot does not guarantee winning trades."
        )


async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Not authorized.")
        return

    rows = get_recent_signals(10)

    if not rows:
        await update.message.reply_text(
            "No signal history available."
        )
        return

    lines = ["📚 RECENT SIGNAL HISTORY"]

    for item in rows:
        lines.append(
            f"\n{item['pair']} | {item['direction']}"
            f"\nPayout: {item['payout']:.0f}%"
            f" | Score: {item['score']}/6"
            f"\nStatus: {item['status']}"
            f"\nID: {item['signal_id']}"
        )

    await update.message.reply_text("\n".join(lines))


async def photo_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "ছবি পেয়েছি। কিন্তু শুধু ছবির ভিত্তিতে নির্ভরযোগ্য "
        "OHLC Candle বা payout নিশ্চিত করা যায় না।\n\n"
        "যাচাইকৃত Scanner data পাঠাতে হবে।"
    )


async def unknown_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "Please use the menu or /start."
    )


def send_signal_to_admins(signal):
    global bot_application, bot_loop

    if not ADMIN_IDS or bot_application is None or bot_loop is None:
        logger.info("Signal saved; no Telegram admin delivery configured.")
        return

    message = format_signal(signal)

    for admin_id in ADMIN_IDS:
        try:
            future = asyncio.run_coroutine_threadsafe(
                bot_application.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                ),
                bot_loop,
            )
            future.result(timeout=10)
        except Exception:
            logger.exception(
                "Could not send signal to admin %s",
                admin_id,
            )


async def run_telegram_bot():
    global bot_application, bot_loop

    bot_loop = asyncio.get_running_loop()

    bot_application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    bot_application.add_handler(
        CommandHandler("start", start_command)
    )
    bot_application.add_handler(
        CommandHandler("history", history_command)
    )
    bot_application.add_handler(
        CallbackQueryHandler(menu_callback)
    )
    bot_application.add_handler(
        MessageHandler(filters.PHOTO, photo_message)
    )
    bot_application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            unknown_message,
        )
    )

    await bot_application.initialize()
    await bot_application.start()

    if bot_application.updater is None:
        raise RuntimeError("Telegram updater is unavailable.")

    await bot_application.updater.start_polling()

    logger.info("%s Telegram bot started.", APP_NAME)

    # Keep the bot event loop alive.
    await asyncio.Event().wait()


def telegram_thread():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing. Telegram bot not started.")
        return

    try:
        asyncio.run(run_telegram_bot())
    except Exception:
        logger.exception("Telegram bot stopped unexpectedly.")


# =========================================================
# STARTUP
# =========================================================

if __name__ == "__main__":
    init_database()

    threading.Thread(
        target=telegram_thread,
        name="telegram-bot",
        daemon=True,
    ).start()

    logger.info("%s HTTP server starting on port %s", APP_NAME, PORT)

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
    )