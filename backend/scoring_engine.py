"""Stock Scoring Engine — multi-stock ranking core.

Computes a weighted score for each stock based on:
  - trend_strength (0.35)
  - volume_signal   (0.20)
  - volatility_adjusted_return (0.20)
  - ai_confidence   (0.15)
  - momentum_score  (0.10)

All analysis is bound to a MarketSnapshot snapshot_id to prevent stale data.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

import numpy as np
import pandas as pd

from backtest_engine import compute_metrics, compute_signals, run_backtest
from data_fetcher import load_data
from market_service import MarketSnapshot, StockRealtimeQuote

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

SCORE_WEIGHTS = {
    "trend_strength": 0.35,
    "volume_signal": 0.20,
    "volatility_adjusted_return": 0.20,
    "ai_confidence": 0.15,
    "momentum_score": 0.10,
}


@dataclass(frozen=True)
class StockScoreResult:
    """Scoring result for a single stock, bound to a market snapshot."""

    stock_code: str
    stock_name: str
    score: float  # 0–100
    trend_strength: float  # sub-score
    volume_signal: float
    volatility_adjusted_return: float
    ai_confidence: float
    momentum_score: float
    reason: str  # plain-language summary
    snapshot_id: str


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
    """
    if signals_df.empty or "position" not in signals_df.columns:
        return 0.0

    # Fraction of time spent in LONG position (recent bias)
    recent = signals_df.tail(min(60, len(signals_df)))
    long_ratio = (recent["position"] > 0).mean()
    trend_up_ratio = long_ratio  # position > 0 means trend-up

    # MA alignment at latest bar
    last = signals_df.iloc[-1]
    ma_bullish = False
    if "MA5" in signals_df.columns and "MA20" in signals_df.columns:
        ma5 = last.get("MA5")
        ma20 = last.get("MA20")
        if pd.notna(ma5) and pd.notna(ma20):
            ma_bullish = float(ma5) > float(ma20)

    score = 0.4 * trend_up_ratio + 0.6 * (1.0 if ma_bullish else 0.0)
    return min(max(score, 0.0), 1.0)


def _compute_volume_signal(signals_df: pd.DataFrame, quote: StockRealtimeQuote) -> float:
    """Score 0–1: volume trend signal.

    Higher score when recent volume is above average (buying interest).
    """
    # Use the real-time quote's volume ratio intuition
    # If quote shows price rising on volume, that's positive
    if quote.change_pct > 0.02 and quote.volume > 0:
        return 0.8
    if quote.change_pct > 0 and quote.volume > 0:
        return 0.6
    if quote.change_pct < -0.02:
        return 0.2
    if quote.change_pct < 0:
        return 0.4
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
    """
    if signals_df.empty or "close" not in signals_df.columns:
        return 0.0

    closes = signals_df["close"].dropna().values
    if len(closes) < 10:
        return 0.0

    ret_5d = (closes[-1] - closes[-5]) / closes[-5] if len(closes) >= 5 else 0.0
    ret_10d = (closes[-1] - closes[-10]) / closes[-10] if len(closes) >= 10 else 0.0

    # Positive and accelerating momentum
    if ret_5d > 0.03 and ret_10d > 0.05:
        return 0.9
    if ret_5d > 0.01 and ret_10d > 0.02:
        return 0.7
    if ret_5d > 0:
        return 0.5
    if ret_5d > -0.02:
        return 0.3
    return 0.1


def _build_reason(
    trend: float,
    volume: float,
    vol_adj: float,
    momentum: float,
    quote: StockRealtimeQuote,
) -> str:
    """Generate a plain-language reason for the score."""
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
) -> Optional[StockScoreResult]:
    """Score a single stock based on available data + real-time quote."""
    try:
        # Load ~1 year of daily data for analysis
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

    # ai_confidence starts at 0.5 neutral; AI module can override later
    ai_conf = 0.5

    raw_score = (
        trend * SCORE_WEIGHTS["trend_strength"]
        + volume * SCORE_WEIGHTS["volume_signal"]
        + vol_adj * SCORE_WEIGHTS["volatility_adjusted_return"]
        + ai_conf * SCORE_WEIGHTS["ai_confidence"]
        + momentum * SCORE_WEIGHTS["momentum_score"]
    )
    score = round(raw_score * 100, 1)  # 0–100 scale
    reason = _build_reason(trend, volume, vol_adj, momentum, quote)

    return StockScoreResult(
        stock_code=stock_code,
        stock_name=stock_name,
        score=score,
        trend_strength=round(trend, 3),
        volume_signal=round(volume, 3),
        volatility_adjusted_return=round(vol_adj, 3),
        ai_confidence=round(ai_conf, 3),
        momentum_score=round(momentum, 3),
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