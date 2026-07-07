"""Stock Scoring Engine — multi-stock ranking core (8-factor model).

Computes a weighted score for each stock based on:
  - trend_strength                (0.25)
  - volume_signal                 (0.15)
  - volatility_adjusted_return    (0.13)
  - ai_confidence                 (0.10)
  - momentum_score                (0.07)
  - valuation_score               (0.12) — PE/PB percentile
  - profitability_score           (0.10) — ROE, net margin
  - growth_score                  (0.08) — revenue/profit growth

Total = 1.00. Factors 1-5 are technical, 6-8 are fundamental.

All analysis is bound to a MarketSnapshot snapshot_id to prevent stale data.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

import numpy as np
import pandas as pd

from backtest_engine import compute_metrics, compute_signals, run_backtest
from data_fetcher import load_data
from financial_analyzer import FinancialMetrics, get_financial_metrics
from market_service import MarketSnapshot, StockRealtimeQuote
from technical_indicators import (
    add_all_indicators,
    compute_indicator_signals,
    composite_technical_score,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weights — 8-factor model (technical 0.70 + fundamental 0.30)
# ---------------------------------------------------------------------------

SCORE_WEIGHTS = {
    "trend_strength": 0.25,
    "volume_signal": 0.15,
    "volatility_adjusted_return": 0.13,
    "ai_confidence": 0.10,
    "momentum_score": 0.07,
    "valuation_score": 0.12,
    "profitability_score": 0.10,
    "growth_score": 0.08,
}


@dataclass(frozen=True)
class StockScoreResult:
    """Scoring result for a single stock, bound to a market snapshot."""

    stock_code: str
    stock_name: str
    score: float  # 0–100
    # Technical factors
    trend_strength: float  # sub-score
    volume_signal: float
    volatility_adjusted_return: float
    ai_confidence: float
    momentum_score: float
    # Fundamental factors (NEW)
    valuation_score: float = 0.5
    profitability_score: float = 0.5
    growth_score: float = 0.5
    # Raw financial data
    financial_metrics: Optional[FinancialMetrics] = None
    # NEW: Technical indicator signals (MACD, RSI, BB, KDJ, ATR)
    indicator_signals: Optional[dict] = None
    composite_indicator_score: float = 0.5  # Combined indicator score 0-1
    # Reason
    reason: str = ""  # plain-language summary
    snapshot_id: str = ""


@dataclass(frozen=True)
class StockRanking:
    """Ranked list of stocks from a single market snapshot."""

    snapshot_id: str
    timestamp: str
    market_state: str
    rankings: list[StockScoreResult]  # sorted by score descending
    top_n: int = 10


# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------


def _compute_trend_strength(signals_df: pd.DataFrame) -> float:
    """Score 0–1: how strong/consistent the trend is.

    Looks at whether MA5 > MA20 (bullish alignment) and position duration.
    Returns near 0 for sustained downtrends.
    """
    if signals_df.empty or "position" not in signals_df.columns:
        return 0.0

    # Fraction of time spent in LONG position (recent bias)
    recent = signals_df.tail(min(60, len(signals_df)))
    long_ratio = (recent["position"] > 0).mean()

    # MA alignment at latest bar
    last = signals_df.iloc[-1]
    ma_bullish = False
    ma_bearish = False
    if "MA5" in signals_df.columns and "MA20" in signals_df.columns:
        ma5 = last.get("MA5")
        ma20 = last.get("MA20")
        if pd.notna(ma5) and pd.notna(ma20):
            ma_bullish = float(ma5) > float(ma20)
            ma_bearish = float(ma5) < float(ma20)

    # Also check closing price trend (recent bias)
    if "close" in signals_df.columns:
        closes = signals_df["close"].dropna().values
        if len(closes) >= 10:
            ret_10d = (closes[-1] - closes[-10]) / closes[-10]
        else:
            ret_10d = 0.0
    else:
        ret_10d = 0.0

    # Penalize strongly when both MA and price are bearish
    if ma_bearish and ret_10d < -0.02:
        return max(0.1, 0.3 * long_ratio + 0.3 * (0.0 if ma_bearish else 0.5) + 0.4 * max(0.0, ret_10d * 10))
    if ma_bearish:
        return max(0.15, 0.4 * long_ratio + 0.3 * 0.0 + 0.3 * max(0.0, ret_10d * 10))

    score = 0.4 * long_ratio + 0.6 * (1.0 if ma_bullish else 0.0)
    return min(max(score, 0.0), 1.0)


def _compute_volume_signal(signals_df: pd.DataFrame, quote: StockRealtimeQuote) -> float:
    """Score 0–1: volume trend signal.

    Higher score when recent volume is above average (buying interest).
    Lower score for heavy selling pressure.
    """
    # Price up on volume: strong bullish
    if quote.change_pct > 0.02 and quote.volume > 0:
        return 0.8
    # Price up: mildly bullish
    if quote.change_pct > 0 and quote.volume > 0:
        return 0.6
    # Price flat
    if abs(quote.change_pct) < 0.005:
        return 0.4
    # Price down: bearish
    if quote.change_pct < -0.03:
        return 0.05  # near zero for heavy selloff
    if quote.change_pct < -0.02:
        return 0.1  # very low
    if quote.change_pct < 0:
        return 0.25  # mildly bearish
    return 0.5


def _compute_volatility_adjusted_return(signals_df: pd.DataFrame) -> float:
    """Score 0–1: recent return adjusted for volatility.

    Higher score for good returns with low volatility.
    """
    if signals_df.empty or "close" not in signals_df.columns:
        return 0.0

    closes = signals_df["close"].dropna().values
    if len(closes) < 20:
        return 0.0

    recent_returns = closes[-20:] / closes[-21:-1] - 1  # daily returns
    total_return = np.prod(1 + recent_returns) - 1

    vol = float(np.std(recent_returns)) if len(recent_returns) > 1 else 0.0
    if vol < 0.001:
        return 0.5  # flat but stable

    sharpe_like = total_return / vol
    # Normalize to 0–1: sharpe of 2.0 → 1.0, sharpe of -1.0 → 0.0
    normalized = (sharpe_like + 1.0) / 3.0
    return min(max(normalized, 0.0), 1.0)


def _compute_momentum_score(signals_df: pd.DataFrame) -> float:
    """Score 0–1: short-term momentum.

    Higher score when recent price change is positive and accelerating.
    Near 0 for sustained declines.
    """
    if signals_df.empty or "close" not in signals_df.columns:
        return 0.0

    closes = signals_df["close"].dropna().values
    if len(closes) < 10:
        return 0.0

    ret_5d = (closes[-1] - closes[-5]) / closes[-5] if len(closes) >= 5 else 0.0
    ret_10d = (closes[-1] - closes[-10]) / closes[-10] if len(closes) >= 10 else 0.0

    # Strong uptrend
    if ret_5d > 0.03 and ret_10d > 0.05:
        return 0.9
    if ret_5d > 0.01 and ret_10d > 0.02:
        return 0.7
    # Mild uptrend
    if ret_5d > 0:
        return 0.55
    # Mild downtrend (0 to -2%)
    if ret_5d > -0.02:
        return 0.25
    # Moderate downtrend (-2% to -5%)
    if ret_5d > -0.05:
        return 0.10
    # Heavy selloff (more than -5%)
    return 0.02


def _compute_valuation_score(fin: Optional[FinancialMetrics]) -> float:
    """Score 0–1: valuation reasonability.

    PE_TTM scoring (relative to A-share average ~20):
      - PE 8-18:   undervalued/good       → 0.8-1.0
      - PE 18-25:  fair                   → 0.6
      - PE 25-35:  slightly rich          → 0.4
      - PE >35 or negative:  expensive    → 0.1-0.3
      - No data: neutral                  → 0.5
    """
    if fin is None or fin.pe_ttm is None:
        return 0.5
    pe = fin.pe_ttm
    if pe <= 0:
        return 0.15  # negative earnings = risky
    if pe <= 10:
        return 0.90  # very undervalued
    if pe <= 15:
        return 0.80
    if pe <= 20:
        return 0.65
    if pe <= 25:
        return 0.50
    if pe <= 30:
        return 0.35
    if pe <= 40:
        return 0.25
    return 0.15


def _compute_profitability_score(fin: Optional[FinancialMetrics]) -> float:
    """Score 0–1: profitability strength.

    Combines ROE and net profit margin.
    """
    if fin is None:
        return 0.5

    roe_score = 0.5
    if fin.roe is not None:
        if fin.roe >= 20:
            roe_score = 1.0
        elif fin.roe >= 15:
            roe_score = 0.85
        elif fin.roe >= 10:
            roe_score = 0.70
        elif fin.roe >= 5:
            roe_score = 0.50
        elif fin.roe >= 0:
            roe_score = 0.30
        else:
            roe_score = 0.10

    margin_score = 0.5
    if fin.net_profit_margin is not None:
        npm = fin.net_profit_margin
        if npm >= 25:
            margin_score = 1.0
        elif npm >= 15:
            margin_score = 0.85
        elif npm >= 10:
            margin_score = 0.70
        elif npm >= 5:
            margin_score = 0.50
        elif npm >= 0:
            margin_score = 0.30
        else:
            margin_score = 0.05

    return 0.6 * roe_score + 0.4 * margin_score


def _compute_growth_score(fin: Optional[FinancialMetrics]) -> float:
    """Score 0–1: growth momentum.

    Combines revenue growth and net profit growth.
    """
    if fin is None:
        return 0.5

    rev_score = 0.5
    if fin.revenue_growth is not None:
        rg = fin.revenue_growth
        if rg >= 30:
            rev_score = 1.0
        elif rg >= 20:
            rev_score = 0.85
        elif rg >= 10:
            rev_score = 0.70
        elif rg >= 0:
            rev_score = 0.50
        elif rg >= -10:
            rev_score = 0.30
        elif rg >= -20:
            rev_score = 0.15
        else:
            rev_score = 0.05

    profit_score = 0.5
    if fin.net_profit_growth is not None:
        ng = fin.net_profit_growth
        if ng >= 30:
            profit_score = 1.0
        elif ng >= 20:
            profit_score = 0.85
        elif ng >= 10:
            profit_score = 0.70
        elif ng >= 0:
            profit_score = 0.50
        elif ng >= -10:
            profit_score = 0.25
        elif ng >= -20:
            profit_score = 0.10
        else:
            profit_score = 0.02

    return 0.4 * rev_score + 0.6 * profit_score


def _build_reason(
    trend: float,
    volume: float,
    vol_adj: float,
    momentum: float,
    quote: StockRealtimeQuote,
    fin: Optional[FinancialMetrics] = None,
    val_score: float = 0.5,
    prof_score: float = 0.5,
    grow_score: float = 0.5,
    indicator_signals: Optional[dict] = None,
) -> str:
    """Generate a plain-language reason for the score, including financial data and technical indicators."""
    parts: list[str] = []

    if trend > 0.7:
        parts.append("上涨趋势增强")
    elif trend > 0.4:
        parts.append("趋势偏弱")
    else:
        parts.append("趋势偏空")

    if volume > 0.6:
        parts.append("成交量放大")
    elif volume < 0.3:
        parts.append("成交量萎缩")

    if momentum > 0.7:
        parts.append("短期动能强劲")
    elif momentum < 0.3:
        parts.append("短期动能不足")

    if quote.change_pct > 0.02:
        parts.append("今日涨幅较大")
    elif quote.change_pct < -0.02:
        parts.append("今日跌幅较大")

    # ── Technical indicator signals ──
    if indicator_signals:
        macd = indicator_signals.get("macd", {})
        rsi = indicator_signals.get("rsi", {})
        bb = indicator_signals.get("bollinger", {})
        kdj = indicator_signals.get("kdj", {})

        if macd.get("signal") == "golden_cross":
            parts.append("MACD金叉")
        elif macd.get("signal") == "death_cross":
            parts.append("MACD死叉")

        if rsi.get("signal") == "overbought":
            parts.append("RSI超买")
        elif rsi.get("signal") == "oversold":
            parts.append("RSI超卖")

        if bb.get("signal") == "squeeze":
            parts.append("布林带收窄")

        if kdj.get("signal") == "overbought":
            parts.append("KDJ超买")
        elif kdj.get("signal") == "oversold":
            parts.append("KDJ超卖")
        elif kdj.get("signal") == "neutral" and kdj.get("score", 0) > 0.7:
            parts.append("KDJ金叉")

    # Financial reasoning
    if fin and fin.has_data:
        if val_score >= 0.65:
            parts.append("估值偏低")
        elif val_score <= 0.30:
            parts.append("估值偏高")

        if prof_score >= 0.70:
            parts.append("盈利能力较强")
        elif prof_score <= 0.30:
            parts.append("盈利能力偏弱")

        if grow_score >= 0.70:
            parts.append("成长性良好")
        elif grow_score <= 0.30:
            parts.append("成长性不足")

    return "；".join(parts) if parts else "市场信号不明确"


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_SCORE_CACHE: dict[str, tuple[StockRanking, float]] = {}
_SCORE_CACHE_LOCK = Lock()
SCORE_CACHE_TTL = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Main scoring engine
# ---------------------------------------------------------------------------


def score_single_stock(
    stock_code: str,
    stock_name: str,
    quote: StockRealtimeQuote,
    snapshot_id: str,
    lookback_days: int = 365,
    include_financial: bool = True,
) -> Optional[StockScoreResult]:
    """Score a single stock based on available data + real-time quote.

    Now includes 8 factors: 5 technical + 3 financial (when available).
    """
    try:
        df = load_data(
            stock_code,
            start_date=pd.Timestamp.today() - pd.Timedelta(days=lookback_days + 30),
            end_date=pd.Timestamp.today().strftime("%Y-%m-%d"),
        )
    except Exception:
        return None

    if df.empty:
        return None

    try:
        signals = compute_signals(df, fast_window=5, slow_window=20, trend_window=60)
        backtest = run_backtest(df, signals)
    except Exception:
        return None

    trend = _compute_trend_strength(signals)
    volume = _compute_volume_signal(signals, quote)
    vol_adj = _compute_volatility_adjusted_return(signals)
    momentum = _compute_momentum_score(signals)
    ai_conf = 0.5  # neutral start; AI module overrides later

    # Financial factors
    fin: Optional[FinancialMetrics] = None
    val_score = 0.5
    prof_score = 0.5
    grow_score = 0.5
    if include_financial:
        try:
            fin = get_financial_metrics(stock_code, stock_name)
            if fin and fin.has_data:
                val_score = _compute_valuation_score(fin)
                prof_score = _compute_profitability_score(fin)
                grow_score = _compute_growth_score(fin)
        except Exception as e:
            logger.debug("Financial scoring skipped for %s: %s", stock_code, e)

    # NEW: Technical indicator signals (MACD, RSI, BB, KDJ, ATR)
    indicator_data: Optional[dict] = None
    composite_ind = 0.5
    try:
        # Use the same signals_df data that already has close/high/low
        if "high" in signals.columns and "low" in signals.columns:
            indicator_data = compute_indicator_signals(signals)
        else:
            # Fallback: merge from the original df
            full_df = signals.copy()
            # Add high/low from original df if missing
            if "high" not in full_df.columns and "high" in df.columns:
                full_df["high"] = df["high"]
            if "low" not in full_df.columns and "low" in df.columns:
                full_df["low"] = df["low"]
            indicator_data = compute_indicator_signals(full_df)
        composite_ind = composite_technical_score(indicator_data)
    except Exception as e:
        logger.debug("Indicator computation skipped for %s: %s", stock_code, e)

    # Enhance trend_strength with indicator data
    trend_enhanced = trend * 0.6 + composite_ind * 0.4

    raw_score = (
        trend_enhanced * SCORE_WEIGHTS["trend_strength"]
        + volume * SCORE_WEIGHTS["volume_signal"]
        + vol_adj * SCORE_WEIGHTS["volatility_adjusted_return"]
        + ai_conf * SCORE_WEIGHTS["ai_confidence"]
        + momentum * SCORE_WEIGHTS["momentum_score"]
        + val_score * SCORE_WEIGHTS["valuation_score"]
        + prof_score * SCORE_WEIGHTS["profitability_score"]
        + grow_score * SCORE_WEIGHTS["growth_score"]
    )
    score = round(raw_score * 100, 1)
    # Use indicator-enhanced trend strength for the reason builder
    reason_trend = trend_enhanced
    reason = _build_reason(reason_trend, volume, vol_adj, momentum, quote, fin, val_score, prof_score, grow_score, indicator_data)

    return StockScoreResult(
        stock_code=stock_code,
        stock_name=stock_name,
        score=score,
        trend_strength=round(trend, 3),
        volume_signal=round(volume, 3),
        volatility_adjusted_return=round(vol_adj, 3),
        ai_confidence=round(ai_conf, 3),
        momentum_score=round(momentum, 3),
        valuation_score=round(val_score, 3),
        profitability_score=round(prof_score, 3),
        growth_score=round(grow_score, 3),
        financial_metrics=fin,
        indicator_signals=indicator_data,
        composite_indicator_score=round(composite_ind, 3),
        reason=reason,
        snapshot_id=snapshot_id,
    )


def rank_stocks(
    market_snapshot: MarketSnapshot,
    top_n: int = 10,
    force_refresh: bool = False,
) -> StockRanking:
    """Score and rank all stocks in a market snapshot.

    Results are cached for SCORE_CACHE_TTL seconds per snapshot.
    """
    cache_key = f"ranking:{market_snapshot.snapshot_id}"

    if not force_refresh:
        with _SCORE_CACHE_LOCK:
            cached = _SCORE_CACHE.get(cache_key)
            if cached and (time.time() - cached[1]) < SCORE_CACHE_TTL:
                return cached[0]

    results: list[StockScoreResult] = []
    for code, quote in market_snapshot.stock_data_map.items():
        scored = score_single_stock(
            stock_code=code,
            stock_name=quote.stock_name,
            quote=quote,
            snapshot_id=market_snapshot.snapshot_id,
        )
        if scored is not None:
            results.append(scored)

    results.sort(key=lambda r: r.score, reverse=True)
    ranking = StockRanking(
        snapshot_id=market_snapshot.snapshot_id,
        timestamp=market_snapshot.timestamp,
        market_state=market_snapshot.market_state,
        rankings=results[:top_n],
        top_n=top_n,
    )

    with _SCORE_CACHE_LOCK:
        _SCORE_CACHE[cache_key] = (ranking, time.time())

    return ranking


def get_cached_ranking(snapshot_id: str) -> Optional[StockRanking]:
    """Return cached ranking for a snapshot, if still fresh."""
    cache_key = f"ranking:{snapshot_id}"
    with _SCORE_CACHE_LOCK:
        cached = _SCORE_CACHE.get(cache_key)
        if cached and (time.time() - cached[1]) < SCORE_CACHE_TTL:
            return cached[0]
    return None


def update_ai_confidence(
    stock_code: str,
    ai_confidence: float,
    snapshot_id: str,
) -> None:
    """Update the ai_confidence sub-score for a stock and re-rank.

    Called by the AI module after it generates a recommendation for a stock.
    Preserves financial factor scores.
    """
    cache_key = f"ranking:{snapshot_id}"
    with _SCORE_CACHE_LOCK:
        cached = _SCORE_CACHE.get(cache_key)
        if not cached:
            return
        ranking = cached[0]

        new_results: list[StockScoreResult] = []
        for r in ranking.rankings:
            if r.stock_code == stock_code:
                conf = max(0.0, min(1.0, ai_confidence))
                raw = (
                    r.trend_strength * SCORE_WEIGHTS["trend_strength"]
                    + r.volume_signal * SCORE_WEIGHTS["volume_signal"]
                    + r.volatility_adjusted_return * SCORE_WEIGHTS["volatility_adjusted_return"]
                    + conf * SCORE_WEIGHTS["ai_confidence"]
                    + r.momentum_score * SCORE_WEIGHTS["momentum_score"]
                    + r.valuation_score * SCORE_WEIGHTS["valuation_score"]
                    + r.profitability_score * SCORE_WEIGHTS["profitability_score"]
                    + r.growth_score * SCORE_WEIGHTS["growth_score"]
                )
                new_score = round(raw * 100, 1)
                new_results.append(StockScoreResult(
                    stock_code=r.stock_code,
                    stock_name=r.stock_name,
                    score=new_score,
                    trend_strength=r.trend_strength,
                    volume_signal=r.volume_signal,
                    volatility_adjusted_return=r.volatility_adjusted_return,
                    ai_confidence=conf,
                    momentum_score=r.momentum_score,
                    valuation_score=r.valuation_score,
                    profitability_score=r.profitability_score,
                    growth_score=r.growth_score,
                    financial_metrics=r.financial_metrics,
                    indicator_signals=r.indicator_signals,
                    composite_indicator_score=r.composite_indicator_score,
                    reason=r.reason,
                    snapshot_id=r.snapshot_id,
                ))
            else:
                new_results.append(r)

        new_results.sort(key=lambda r: r.score, reverse=True)
        new_ranking = StockRanking(
            snapshot_id=ranking.snapshot_id,
            timestamp=ranking.timestamp,
            market_state=ranking.market_state,
            rankings=new_results,
            top_n=ranking.top_n,
        )
        _SCORE_CACHE[cache_key] = (new_ranking, time.time())