"""Deterministic indicator engine for FINOREX PREMIUM BOT.

Consumes user-supplied OHLC candles only. It does not fetch or invent broker data.
"""
from __future__ import annotations
from math import sqrt
from typing import Iterable

class MarketDataError(ValueError):
    pass

def _validate(candles: Iterable[dict]) -> list[dict[str, float]]:
    out = []
    for index, candle in enumerate(candles, 1):
        try:
            o, h, l, c = (float(candle[k]) for k in ("open", "high", "low", "close"))
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError(f"Candle {index}: invalid OHLC fields") from exc
        if min(o, h, l, c) <= 0 or l > min(o, c) or h < max(o, c) or l > h:
            raise MarketDataError(f"Candle {index}: impossible OHLC values")
        out.append({"open": o, "high": h, "low": l, "close": c})
    if len(out) < 60:
        raise MarketDataError("At least 60 valid candles are required for this indicator set")
    return out

def sma(values: list[float], period: int) -> float:
    if len(values) < period:
        raise MarketDataError(f"Need {period} values for SMA")
    return sum(values[-period:]) / period

def ema_series(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        raise MarketDataError(f"Need {period} values for EMA")
    alpha = 2.0 / (period + 1)
    current = sum(values[:period]) / period
    result = [current]
    for value in values[period:]:
        current = alpha * value + (1.0 - alpha) * current
        result.append(current)
    return result

def rsi_wilder(values: list[float], period: int = 14) -> float:
    if len(values) <= period:
        raise MarketDataError("Not enough candles for RSI")
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(x, 0.0) for x in changes]
    losses = [max(-x, 0.0) for x in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = ((period - 1) * avg_gain + gain) / period
        avg_loss = ((period - 1) * avg_loss + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def analyze(candles: Iterable[dict], payout: int | None = None) -> dict:
    rows = _validate(candles)
    if payout is not None and not 80 <= int(payout) <= 100:
        return {"decision": "WAIT", "reason": "Payout is below 80% or invalid", "eligible": False}
    close = [x["close"] for x in rows]
    high = [x["high"] for x in rows]
    low = [x["low"] for x in rows]
    ema9, ema21 = ema_series(close, 9)[-1], ema_series(close, 21)[-1]
    sma20, sma50 = sma(close, 20), sma(close, 50)
    fast, slow = ema_series(close, 12), ema_series(close, 26)
    macd_history = [a - b for a, b in zip(fast, slow)]
    macd_line = macd_history[-1]
    signal_line = ema_series(macd_history, 9)[-1]
    macd_hist = macd_line - signal_line
    rsi = rsi_wilder(close)
    window = close[-20:]
    mid = sum(window) / 20
    deviation = 2.0 * sqrt(sum((x - mid) ** 2 for x in window) / 20)
    upper, lower = mid + deviation, mid - deviation
    ranges = [h - l for h, l in zip(high, low)]
    avg_range = sum(ranges[-20:]) / 20
    if avg_range <= 0:
        return {"decision": "WAIT", "reason": "Insufficient candle movement", "eligible": False}
    if ranges[-1] > avg_range * 2.5:
        return {"decision": "WAIT", "reason": "Abnormally large latest candle; volatility filter rejected", "eligible": False}
    bullish_trend = ema9 > ema21 and sma20 > sma50 and close[-1] > sma20
    bearish_trend = ema9 < ema21 and sma20 < sma50 and close[-1] < sma20
    bullish_momentum = macd_hist > 0 and 50 < rsi < 68
    bearish_momentum = macd_hist < 0 and 32 < rsi < 50
    inside_bands = lower <= close[-1] <= upper
    if bullish_trend and bullish_momentum and inside_bands:
        decision, reason = "UP", "Trend and momentum align; close remains inside Bollinger Bands"
    elif bearish_trend and bearish_momentum and inside_bands:
        decision, reason = "DOWN", "Trend and momentum align; close remains inside Bollinger Bands"
    else:
        decision, reason = "WAIT", "Indicators are not sufficiently aligned; NO-TRADE"
    return {
        "decision": decision, "reason": reason,
        "eligible": decision in ("UP", "DOWN") and payout is not None,
        "payout": payout,
        "indicators": {
            "EMA9": round(ema9, 8), "EMA21": round(ema21, 8),
            "SMA20": round(sma20, 8), "SMA50": round(sma50, 8),
            "MACD": round(macd_line, 8), "MACD_signal": round(signal_line, 8),
            "MACD_histogram": round(macd_hist, 8), "RSI14": round(rsi, 2),
            "BB_upper": round(upper, 8), "BB_middle": round(mid, 8),
            "BB_lower": round(lower, 8), "average_range_20": round(avg_range, 8),
        },
        "checks": {
            "trend": bullish_trend or bearish_trend,
            "momentum": bullish_momentum or bearish_momentum,
            "bollinger_inside": inside_bands,
            "volatility": True,
            "payout_at_least_80": payout is not None and 80 <= int(payout) <= 100,
        },
    }
