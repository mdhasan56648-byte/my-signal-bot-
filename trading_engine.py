
"""Deterministic technical analysis engine for FINOREX PREMIUM BOT.

Uses only user-supplied OHLC candles.
No simulated prices, broker API, or invented payout data.
"""

from __future__ import annotations

from math import sqrt
from typing import Iterable


class MarketDataError(ValueError):
    """Raised when candle data is invalid or insufficient."""


MIN_CANDLES = 60
MIN_PAYOUT = 80.0
MAX_PAYOUT = 100.0


def _validate(candles: Iterable[dict]) -> list[dict[str, float]]:
    rows = []

    for index, candle in enumerate(candles, 1):
        try:
            o, h, l, c = (
                float(candle[key])
                for key in ("open", "high", "low", "close")
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError(
                f"Candle {index}: invalid OHLC fields"
            ) from exc

        values = (o, h, l, c)

        if any(not (0 < value < float("inf")) for value in values):
            raise MarketDataError(
                f"Candle {index}: prices must be positive and finite"
            )

        if l > min(o, c) or h < max(o, c) or l > h:
            raise MarketDataError(
                f"Candle {index}: impossible OHLC values"
            )

        rows.append({
            "open": o,
            "high": h,
            "low": l,
            "close": c,
        })

    if len(rows) < MIN_CANDLES:
        raise MarketDataError(
            f"At least {MIN_CANDLES} valid candles are required"
        )

    return rows


def sma(values: list[float], period: int) -> float:
    if period <= 0 or len(values) < period:
        raise MarketDataError(f"Not enough values for SMA {period}")

    return sum(values[-period:]) / period


def ema_series(values: list[float], period: int) -> list[float]:
    if period <= 0 or len(values) < period:
        raise MarketDataError(f"Not enough values for EMA {period}")

    alpha = 2.0 / (period + 1)
    current = sum(values[:period]) / period
    result = [current]

    for value in values[period:]:
        current = alpha * value + (1.0 - alpha) * current
        result.append(current)

    return result


def rsi_wilder(values: list[float], period: int = 14) -> float:
    if len(values) <= period:
        raise MarketDataError("Not enough values for RSI")

    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (
            (avg_gain * (period - 1) + gain) / period
        )
        avg_loss = (
            (avg_loss * (period - 1) + loss) / period
        )

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _candlestick_pattern(rows: list[dict]) -> str:
    previous = rows[-2]
    current = rows[-1]

    po, pc = previous["open"], previous["close"]
    o, h, l, c = (
        current["open"],
        current["high"],
        current["low"],
        current["close"],
    )

    body = abs(c - o)
    candle_range = h - l

    if candle_range <= 0:
        return "DOJI"

    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    if (
        pc < po
        and c > o
        and o <= pc
        and c >= po
    ):
        return "BULLISH_ENGULFING"

    if (
        pc > po
        and c < o
        and o >= pc
        and c <= po
    ):
        return "BEARISH_ENGULFING"

    if (
        body <= candle_range * 0.30
        and lower_wick >= body * 2
        and upper_wick <= candle_range * 0.25
    ):
        return "HAMMER"

    if (
        body <= candle_range * 0.30
        and upper_wick >= body * 2
        and lower_wick <= candle_range * 0.25
    ):
        return "SHOOTING_STAR"

    if body <= candle_range * 0.10:
        return "DOJI"

    return "NONE"


def analyze(
    candles: Iterable[dict],
    payout: int | float | None = None,
) -> dict:
    """
    Analyze supplied OHLC candles.

    payout must be independently verified from the broker.
    Unknown payout always produces WAIT.
    """

    rows = _validate(candles)

    closes = [row["close"] for row in rows]
    highs = [row["high"] for row in rows]
    lows = [row["low"] for row in rows]

    if payout is None:
        payout_value = None
    else:
        try:
            payout_value = float(payout)
        except (TypeError, ValueError):
            payout_value = None

    payout_valid = (
        payout_value is not None
        and MIN_PAYOUT <= payout_value <= MAX_PAYOUT
    )

    # Moving averages
    ma10 = sma(closes, 10)
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)

    ema9 = ema_series(closes, 9)[-1]
    ema21 = ema_series(closes, 21)[-1]

    # MACD: align EMA series to the same candle timestamps.
    ema12_series = ema_series(closes, 12)
    ema26_series = ema_series(closes, 26)

    aligned_fast = ema12_series[-len(ema26_series):]

    macd_history = [
        fast - slow
        for fast, slow in zip(
            aligned_fast,
            ema26_series,
        )
    ]

    macd_line = macd_history[-1]
    signal_line = ema_series(macd_history, 9)[-1]
    macd_histogram = macd_line - signal_line

    # RSI
    rsi = rsi_wilder(closes, 14)

    # Bollinger Bands: 20-period, 2 standard deviations.
    window = closes[-20:]
    bb_middle = sum(window) / 20

    deviation = sqrt(
        sum((value - bb_middle) ** 2 for value in window) / 20
    )

    bb_upper = bb_middle + (2 * deviation)
    bb_lower = bb_middle - (2 * deviation)

    latest_close = closes[-1]

    # Candle range and volatility checks.
    ranges = [
        high - low
        for high, low in zip(highs, lows)
    ]

    avg_range = sum(ranges[-20:]) / 20
    previous_avg_range = sum(ranges[-40:-20]) / 20
    latest_range = ranges[-1]

    volatility_ratio = (
        latest_range / avg_range if avg_range > 0 else float("inf")
    )

    volatility_expansion = (
        avg_range / previous_avg_range
        if previous_avg_range > 0
        else float("inf")
    )

    volatility_ok = (
        avg_range > 0
        and volatility_ratio <= 2.5
        and volatility_expansion <= 2.5
    )

    # Trend
    bullish_trend = (
        ema9 > ema21
        and sma20 > sma50
        and latest_close > sma20
    )

    bearish_trend = (
        ema9 < ema21
        and sma20 < sma50
        and latest_close < sma20
    )

    # Momentum
    bullish_momentum = (
        macd_histogram > 0
        and 50 < rsi < 68
    )

    bearish_momentum = (
        macd_histogram < 0
        and 32 < rsi < 50
    )

    # Bollinger position
    inside_bands = bb_lower <= latest_close <= bb_upper

    # Support and resistance from previous 20 candles,
    # excluding the current candle.
    resistance = max(highs[-21:-1])
    support = min(lows[-21:-1])

    breakout = latest_close > resistance
    breakdown = latest_close < support

    # Basic candlestick recognition.
    pattern = _candlestick_pattern(rows)

    bullish_pattern = pattern in (
        "BULLISH_ENGULFING",
        "HAMMER",
    )

    bearish_pattern = pattern in (
        "BEARISH_ENGULFING",
        "SHOOTING_STAR",
    )

    # Score is a technical alignment score, NOT win probability.
    bullish_checks = {
        "trend": bullish_trend,
        "momentum": bullish_momentum,
        "bollinger_position": inside_bands,
        "price_action": latest_close > ma10,
        "breakout": breakout,
        "candlestick": bullish_pattern,
    }

    bearish_checks = {
        "trend": bearish_trend,
        "momentum": bearish_momentum,
        "bollinger_position": inside_bands,
        "price_action": latest_close < ma10,
        "breakdown": breakdown,
        "candlestick": bearish_pattern,
    }

    bullish_score = sum(bullish_checks.values())
    bearish_score = sum(bearish_checks.values())

    decision = "WAIT"
    reason = "Indicators are not sufficiently aligned; NO-TRADE"

    # Strict filters: unknown/low payout and excessive volatility
    # can never produce an eligible signal.
    if not payout_valid:
        reason = "Verified payout is missing or below 80%"

    elif not volatility_ok:
        reason = "Volatility filter rejected the market"

    elif bullish_trend and bullish_momentum and inside_bands:
        if bullish_score >= 4:
            decision = "UP"
            reason = "Bullish trend and momentum are aligned"

    elif bearish_trend and bearish_momentum and inside_bands:
        if bearish_score >= 4:
            decision = "DOWN"
            reason = "Bearish trend and momentum are aligned"

    analysis_score = max(bullish_score, bearish_score)

    return {
        "decision": decision,
        "reason": reason,
        "eligible": decision in ("UP", "DOWN") and payout_valid,
        "payout": payout_value,
        "analysis_score": analysis_score,
        "score_max": 6,

        "indicators": {
            "MA10": round(ma10, 8),
            "EMA9": round(ema9, 8),
            "EMA21": round(ema21, 8),
            "SMA20": round(sma20, 8),
            "SMA50": round(sma50, 8),
            "MACD": round(macd_line, 8),
            "MACD_signal": round(signal_line, 8),
            "MACD_histogram": round(macd_histogram, 8),
            "RSI14": round(rsi, 2),
            "BB_upper": round(bb_upper, 8),
            "BB_middle": round(bb_middle, 8),
            "BB_lower": round(bb_lower, 8),
            "average_range_20": round(avg_range, 8),
            "latest_range": round(latest_range, 8),
            "volatility_ratio": round(volatility_ratio, 3),
            "support": round(support, 8),
            "resistance": round(resistance, 8),
            "candlestick_pattern": pattern,
        },

        "checks": {
            "bullish": bullish_checks,
            "bearish": bearish_checks,
            "volatility": volatility_ok,
            "payout_at_least_80": payout_valid,
            "support_resistance_available": True,
        },
    }
