"""Technical Indicators — MACD, RSI, Bollinger Bands, KDJ, ATR and more.

All functions accept a pandas DataFrame with at least a 'close' column
(and optionally 'high', 'low', 'volume') and return the DataFrame with
new indicator columns appended.

This module is independent of the rest of the system — can be used by
both the backtest engine and the AI advisor scoring engine.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for col in result.columns:
        result[col] = pd.to_numeric(result[col], errors="coerce")
    result = result.replace([np.inf, -np.inf], np.nan)
    return result


# ── MACD ────────────────────────────────────────────────────────────────

def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    col: str = "close",
) -> pd.DataFrame:
    """Add MACD, signal line, and histogram columns.

    Columns added: MACD_{fast}_{slow}, MACD_signal_{signal}, MACD_hist
    """
    result = _clean(df)
    close = result[col]
    ema_fast = close.ewm(span=fast, min_periods=fast).mean()
    ema_slow = close.ewm(span=slow, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm(span=signal, min_periods=signal).mean()
    macd_hist = macd_line - macd_signal

    result[f"MACD_{fast}_{slow}"] = macd_line
    result[f"MACD_signal_{signal}"] = macd_signal
    result["MACD_hist"] = macd_hist
    return result


def macd_signal(macd_line: float, macd_signal_line: float) -> str:
    """Return a simple MACD signal string: 'golden_cross' | 'death_cross' | 'neutral'."""
    if macd_line > macd_signal_line:
        return "golden_cross"
    if macd_line < macd_signal_line:
        return "death_cross"
    return "neutral"


def macd_score(macd_line: float, macd_signal_line: float, macd_hist: float) -> float:
    """Score 0–1: MACD bullishness."""
    base = 0.5
    if macd_line > macd_signal_line:
        base += 0.3
    else:
        base -= 0.2
    if macd_hist > 0:
        base += 0.1
    else:
        base -= 0.1
    # Bullish divergence when MACD > 0 and rising
    if macd_line > 0 and macd_line > macd_signal_line:
        base += 0.1
    return max(0.0, min(1.0, base))


# ── RSI ─────────────────────────────────────────────────────────────────

def add_rsi(
    df: pd.DataFrame,
    period: int = 14,
    col: str = "close",
) -> pd.DataFrame:
    """Add RSI (Relative Strength Index) column.

    Uses Wilder's smoothing (SMA of gains/losses).
    Column added: RSI_{period}
    """
    result = _clean(df)
    close = result[col]
    delta = close.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50.0)

    result[f"RSI_{period}"] = rsi
    return result


def rsi_score(rsi_value: float) -> float:
    """Score 0–1 from RSI (0–100)."""
    if rsi_value >= 70:
        return 0.1  # overbought — caution
    if rsi_value >= 60:
        return 0.6  # bullish
    if rsi_value >= 45:
        return 0.5  # neutral
    if rsi_value >= 30:
        return 0.4  # bearish
    return 0.1  # oversold — risky


def rsi_signal(rsi_value: float) -> str:
    if rsi_value >= 70:
        return "overbought"
    if rsi_value <= 30:
        return "oversold"
    return "neutral"


# ── Bollinger Bands ─────────────────────────────────────────────────────

def add_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
    col: str = "close",
) -> pd.DataFrame:
    """Add Bollinger Bands columns.

    Columns added: BB_middle_{period}, BB_upper_{period}_{std_dev},
                   BB_lower_{period}_{std_dev}, BB_width, BB_pct
    """
    result = _clean(df)
    close = result[col]
    middle = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std()

    upper = middle + std_dev * std
    lower = middle - std_dev * std
    width = (upper - lower) / middle
    bb_pct = (close - lower) / (upper - lower).replace(0, np.nan)

    result[f"BB_middle_{period}"] = middle
    result[f"BB_upper_{period}_{std_dev}"] = upper
    result[f"BB_lower_{period}_{std_dev}"] = lower
    result["BB_width"] = width
    result["BB_pct"] = bb_pct.fillna(0.5)
    return result


def bb_score(bb_pct: float, bb_width: float) -> float:
    """Score 0–1 from Bollinger Bands position.

    BB% near 0.5 (middle) = neutral → 0.5
    BB% near 0 (lower band) = oversold → 0.3 (potential bounce, slightly bearish)
    BB% near 1 (upper band) = overbought → 0.7 (potential pullback, mildly bullish)
    Very wide bands = high volatility → caution
    Very narrow bands = low volatility → potential breakout
    """
    base = 0.5
    # Position within bands
    if bb_pct > 0.8:
        base += 0.2  # near upper band — bullish momentum
    elif bb_pct > 0.5:
        base += 0.1
    elif bb_pct < 0.2:
        base -= 0.2  # near lower band — bearish momentum
    elif bb_pct < 0.5:
        base -= 0.1

    # Width adjustment: narrow bands = squeeze (potential breakout)
    if bb_width < 0.05:
        base += 0.1  # Bollinger squeeze — watch for breakout
    elif bb_width > 0.15:
        base -= 0.05  # too wide — high vol

    return max(0.0, min(1.0, base))


# ── KDJ (Stochastic) ───────────────────────────────────────────────────

def add_kdj(
    df: pd.DataFrame,
    period: int = 9,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> pd.DataFrame:
    """Add KDJ (Stochastic) indicator columns.

    Columns added: KDJ_K_{period}, KDJ_D_{period}, KDJ_J_{period}
    """
    result = _clean(df)
    low_min = result["low"].rolling(window=period, min_periods=period).min()
    high_max = result["high"].rolling(window=period, min_periods=period).max()
    rsv = (result["close"] - low_min) / (high_max - low_min).replace(0, np.nan) * 100

    k_line = rsv.ewm(alpha=1.0 / k_smooth, min_periods=k_smooth, adjust=False).mean()
    d_line = k_line.ewm(alpha=1.0 / d_smooth, min_periods=d_smooth, adjust=False).mean()
    j_line = 3 * k_line - 2 * d_line

    result[f"KDJ_K_{period}"] = k_line.fillna(50)
    result[f"KDJ_D_{period}"] = d_line.fillna(50)
    result[f"KDJ_J_{period}"] = j_line.fillna(50)
    return result


def kdj_score(k_value: float, d_value: float, j_value: float) -> float:
    """Score 0–1 from KDJ."""
    base = 0.5
    if k_value > 80:
        base -= 0.2  # overbought
    elif k_value > 60:
        base += 0.2  # bullish
    elif k_value > 40:
        base += 0.0  # neutral
    elif k_value > 20:
        base -= 0.1  # bearish
    else:
        base -= 0.2  # oversold

    # K > D = bullish
    if k_value > d_value:
        base += 0.1
    else:
        base -= 0.1

    return max(0.0, min(1.0, base))


# ── ATR (Average True Range) ────────────────────────────────────────────

def add_atr(
    df: pd.DataFrame,
    period: int = 14,
) -> pd.DataFrame:
    """Add ATR (Average True Range) column.

    Column added: ATR_{period}
    """
    result = _clean(df)
    high = result["high"]
    low = result["low"]
    close = result["close"]
    prev_close = close.shift(1)

    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(span=period, min_periods=period, adjust=False).mean()
    result[f"ATR_{period}"] = atr.fillna(0)
    return result


# ── Combined indicator computation ──────────────────────────────────────

def add_all_indicators(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Add all technical indicators to a DataFrame.

    Requires columns: close, high, low (volume optional).
    Adds: MACD, RSI, Bollinger Bands, KDJ, ATR
    """
    result = add_macd(df)
    result = add_rsi(result)
    result = add_bollinger_bands(result)
    result = add_kdj(result)
    result = add_atr(result)
    return result


def get_latest_indicators(
    df: pd.DataFrame,
) -> dict[str, float]:
    """Get the latest values of all computed indicators as a flat dict."""
    result = add_all_indicators(df)
    if result.empty:
        return {}

    last = result.iloc[-1]
    out: dict[str, float] = {}

    for col in result.columns:
        if col in ("date", "open", "close", "high", "low", "volume"):
            continue
        val = last.get(col)
        if pd.notna(val) and isinstance(val, (int, float, np.floating)):
            out[col] = round(float(val), 4)
    return out


def compute_indicator_signals(
    df: pd.DataFrame,
) -> dict[str, dict]:
    """Compute all indicator signals with scores (0–1) and text signals.

    Returns a dict like:
    {
        "macd": {"score": 0.7, "signal": "golden_cross", "value": 0.123},
        "rsi": {"score": 0.6, "signal": "neutral", "value": 55.0},
        ...
    }
    """
    result = add_all_indicators(df)
    if result.empty:
        return {}

    last = result.iloc[-1]
    signals: dict[str, dict] = {}

    # MACD
    macd_col = f"MACD_12_26"
    macd_sig_col = "MACD_signal_9"
    macd_hist_col = "MACD_hist"
    if macd_col in result.columns:
        m = float(last.get(macd_col, 0) or 0)
        ms = float(last.get(macd_sig_col, 0) or 0)
        mh = float(last.get(macd_hist_col, 0) or 0)
        signals["macd"] = {
            "score": round(macd_score(m, ms, mh), 3),
            "signal": macd_signal(m, ms),
            "value": round(m, 4),
            "signal_value": round(ms, 4),
            "histogram": round(mh, 4),
        }

    # RSI
    rsi_col = "RSI_14"
    if rsi_col in result.columns:
        r = float(last.get(rsi_col, 50) or 50)
        signals["rsi"] = {
            "score": round(rsi_score(r), 3),
            "signal": rsi_signal(r),
            "value": round(r, 2),
        }

    # Bollinger Bands
    bb_pct_col = "BB_pct"
    bb_width_col = "BB_width"
    if bb_pct_col in result.columns:
        bp = float(last.get(bb_pct_col, 0.5) or 0.5)
        bw = float(last.get(bb_width_col, 0.1) or 0.1)
        signals["bollinger"] = {
            "score": round(bb_score(bp, bw), 3),
            "signal": "squeeze" if bw < 0.05 else "normal",
            "bb_pct": round(bp, 3),
            "bb_width": round(bw, 4),
        }

    # KDJ
    k_col = "KDJ_K_9"
    d_col = "KDJ_D_9"
    j_col = "KDJ_J_9"
    if k_col in result.columns:
        kv = float(last.get(k_col, 50) or 50)
        dv = float(last.get(d_col, 50) or 50)
        jv = float(last.get(j_col, 50) or 50)
        signals["kdj"] = {
            "score": round(kdj_score(kv, dv, jv), 3),
            "signal": "overbought" if kv > 80 else ("oversold" if kv < 20 else "neutral"),
            "K": round(kv, 2),
            "D": round(dv, 2),
            "J": round(jv, 2),
        }

    # ATR
    atr_col = "ATR_14"
    if atr_col in result.columns:
        atr_val = float(last.get(atr_col, 0) or 0)
        avg_price = float(result["close"].tail(14).mean() or 1)
        atr_pct = atr_val / avg_price if avg_price > 0 else 0
        signals["atr"] = {
            "score": round(0.5, 3),  # ATR is descriptive, not directional
            "signal": "high_vol" if atr_pct > 0.05 else ("low_vol" if atr_pct < 0.01 else "normal"),
            "value": round(atr_val, 4),
            "atr_pct": round(atr_pct * 100, 2),
        }

    return signals


def composite_technical_score(signals: dict[str, dict]) -> float:
    """Combine all indicator scores into a single 0–1 technical score.

    Weights: MACD 0.25, RSI 0.25, Bollinger 0.20, KDJ 0.20, ATR 0.10
    """
    weights = {"macd": 0.25, "rsi": 0.25, "bollinger": 0.20, "kdj": 0.20, "atr": 0.10}
    total = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        if key in signals and "score" in signals[key]:
            total += signals[key]["score"] * weight
            weight_sum += weight
    return total / weight_sum if weight_sum > 0 else 0.5


# ── Multi-timeframe support ─────────────────────────────────────────────

def resample_to_weekly(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Resample daily OHLCV data to weekly.

    Input must have: date, open, high, low, close, volume (all numeric).
    'date' must be parseable as datetime.
    """
    result = df.copy()
    result[date_col] = pd.to_datetime(result[date_col])
    result = result.set_index(date_col).sort_index()

    weekly = pd.DataFrame(index=result.resample("W").last().index)
    weekly["open"] = result["open"].resample("W").first()
    weekly["high"] = result["high"].resample("W").max()
    weekly["low"] = result["low"].resample("W").min()
    weekly["close"] = result["close"].resample("W").last()
    weekly["volume"] = result["volume"].resample("W").sum()
    weekly = weekly.dropna(subset=["close"])
    weekly = weekly.reset_index().rename(columns={"index": "date"})
    weekly["date"] = weekly["date"].dt.strftime("%Y-%m-%d")
    return weekly


def resample_to_monthly(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Resample daily OHLCV data to monthly."""
    result = df.copy()
    result[date_col] = pd.to_datetime(result[date_col])
    result = result.set_index(date_col).sort_index()

    monthly = pd.DataFrame(index=result.resample("ME").last().index)
    monthly["open"] = result["open"].resample("ME").first()
    monthly["high"] = result["high"].resample("ME").max()
    monthly["low"] = result["low"].resample("ME").min()
    monthly["close"] = result["close"].resample("ME").last()
    monthly["volume"] = result["volume"].resample("ME").sum()
    monthly = monthly.dropna(subset=["close"])
    monthly = monthly.reset_index().rename(columns={"index": "date"})
    monthly["date"] = monthly["date"].dt.strftime("%Y-%m-%d")
    return monthly


def analyze_timeframe(
    df: pd.DataFrame,
    timeframe: str = "daily",
) -> dict[str, dict]:
    """Run indicator analysis on a specific timeframe.

    Args:
        df: Daily OHLCV DataFrame
        timeframe: 'daily', 'weekly', or 'monthly'

    Returns:
        Indicator signals dictionary as from compute_indicator_signals()
    """
    if timeframe == "weekly":
        tf_df = resample_to_weekly(df)
    elif timeframe == "monthly":
        tf_df = resample_to_monthly(df)
    else:
        tf_df = df.copy()

    if tf_df.empty or len(tf_df) < 30:
        return {}

    return compute_indicator_signals(tf_df)