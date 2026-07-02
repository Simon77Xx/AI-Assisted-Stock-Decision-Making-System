"""Market Data Service — real-time/market data layer for multi-stock analysis.

Provides:
- Real-time stock price fetching via akshare
- Market snapshot with timestamp + stock data map
- TTL-based cache (5 min default)
- Snapshot ID for data version control (prevents stale data usage)
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

import akshare as ak
import pandas as pd

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StockRealtimeQuote:
    """A single stock's real-time market quote."""

    stock_code: str
    stock_name: str
    price: float
    change_pct: float  # e.g. 0.02 = +2%
    volume: float
    amount: float
    turnover: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open_: Optional[float] = None
    prev_close: Optional[float] = None


@dataclass(frozen=True)
class MarketSnapshot:
    """Immutable snapshot of the market at a point in time."""

    snapshot_id: str
    timestamp: str  # ISO-8601
    market_state: str  # "bull" | "bear" | "sideways" | "unknown"
    stock_data_map: dict[str, StockRealtimeQuote]  # code -> quote
    source: str = "akshare"


# ---------------------------------------------------------------------------
# Default stock pools
# ---------------------------------------------------------------------------

# Popular A-share stocks (diversified sectors)
A_SHARE_WATCHLIST = [
    "000001",  # 平安银行
    "000002",  # 万科A
    "000333",  # 美的集团
    "000651",  # 格力电器
    "000858",  # 五粮液
    "002415",  # 海康威视
    "002475",  # 立讯精密
    "300059",  # 东方财富
    "300750",  # 宁德时代
    "600036",  # 招商银行
    "600276",  # 恒瑞医药
    "600519",  # 贵州茅台
    "600887",  # 伊利股份
    "600900",  # 长江电力
    "601318",  # 中国平安
    "601857",  # 中国石油
    "603259",  # 药明康德
    "688981",  # 中芯国际
]

# ---------------------------------------------------------------------------
# Market state inference helpers
# ---------------------------------------------------------------------------


def _infer_market_state(quotes: list[StockRealtimeQuote]) -> str:
    """Infer overall market state from a list of real-time quotes.

    Simple heuristic based on the percentage of stocks rising.
    """
    if not quotes:
        return "unknown"
    rising = sum(1 for q in quotes if q.change_pct > 0)
    ratio = rising / len(quotes)
    if ratio >= 0.6:
        return "bull"
    if ratio <= 0.35:
        return "bear"
    return "sideways"


# ---------------------------------------------------------------------------
# Market data service
# ---------------------------------------------------------------------------


class MarketDataService:
    """TTL-cached market data service backed by akshare."""

    def __init__(self, cache_ttl_seconds: int = 300):
        self._cache_ttl = cache_ttl_seconds
        self._snapshot: Optional[MarketSnapshot] = None
        self._snapshot_time: float = 0.0
        self._lock = Lock()

    # ── public API ──────────────────────────────────────────────────────

    def get_market_snapshot(
        self,
        stock_codes: Optional[list[str]] = None,
        force_refresh: bool = False,
    ) -> MarketSnapshot:
        """Return current market snapshot (with TTL cache).

        If the cache is still fresh and *force_refresh* is False, returns the
        cached snapshot. Otherwise fetches fresh data from akshare.
        """
        now = time.time()
        with self._lock:
            if (
                not force_refresh
                and self._snapshot is not None
                and (now - self._snapshot_time) < self._cache_ttl
            ):
                return self._snapshot

        # Cache miss — fetch fresh data
        codes = stock_codes or A_SHARE_WATCHLIST
        quotes = self._fetch_realtime_quotes(codes)
        market_state = _infer_market_state(list(quotes.values()))
        snapshot = self._build_snapshot(market_state, quotes)

        with self._lock:
            self._snapshot = snapshot
            self._snapshot_time = now
        return snapshot

    def get_stock_quote(
        self,
        stock_code: str,
        force_refresh: bool = False,
    ) -> Optional[StockRealtimeQuote]:
        """Get a single stock's real-time quote."""
        snapshot = self.get_market_snapshot(force_refresh=force_refresh)
        return snapshot.stock_data_map.get(stock_code)

    def refresh(self) -> MarketSnapshot:
        """Force a refresh of the market snapshot."""
        return self.get_market_snapshot(force_refresh=True)

    # ── internal helpers ────────────────────────────────────────────────

    def _fetch_realtime_quotes(
        self,
        stock_codes: list[str],
    ) -> dict[str, StockRealtimeQuote]:
        """Fetch real-time quotes for a list of A-share stock codes.

        Uses akshare's real-time market endpoint which returns all stocks at
        once. We filter to the requested codes.
        """
        try:
            df = ak.stock_zh_a_spot_em()  # real-time A-share snapshot
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch real-time market data: {exc}") from exc

        if df.empty or "代码" not in df.columns:
            return {}

        df["代码"] = df["代码"].astype(str).str.strip()
        filtered = df[df["代码"].isin(stock_codes)]
        if filtered.empty:
            return {}

        quotes: dict[str, StockRealtimeQuote] = {}
        for _, row in filtered.iterrows():
            code = str(row.get("代码", "")).strip()
            name = str(row.get("名称", ""))
            try:
                quote = StockRealtimeQuote(
                    stock_code=code,
                    stock_name=name,
                    price=float(row.get("最新价", 0) or 0),
                    change_pct=float(row.get("涨跌幅", 0) or 0) / 100.0,
                    volume=float(row.get("成交量", 0) or 0),
                    amount=float(row.get("成交额", 0) or 0),
                    turnover=float(row.get("换手率", 0) or None) if "换手率" in df.columns else None,
                    high=float(row.get("最高", 0) or None) if "最高" in df.columns else None,
                    low=float(row.get("最低", 0) or None) if "最低" in df.columns else None,
                    open_=float(row.get("今开", 0) or None) if "今开" in df.columns else None,
                    prev_close=float(row.get("昨收", 0) or None) if "昨收" in df.columns else None,
                )
                quotes[code] = quote
            except (ValueError, TypeError):
                continue

        return quotes

    def _build_snapshot(
        self,
        market_state: str,
        quotes: dict[str, StockRealtimeQuote],
    ) -> MarketSnapshot:
        """Build a MarketSnapshot with a unique ID."""
        now = datetime.now(timezone.utc)
        raw = f"{now.isoformat()}{json.dumps(sorted(quotes.keys()), sort_keys=True)}"
        snapshot_id = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
        return MarketSnapshot(
            snapshot_id=snapshot_id,
            timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
            market_state=market_state,
            stock_data_map=quotes,
        )


# ---------------------------------------------------------------------------
# Singleton (lazy init via get_market_service)
# ---------------------------------------------------------------------------

_market_service: Optional[MarketDataService] = None
_market_service_lock = Lock()


def get_market_service(cache_ttl_seconds: int = 300) -> MarketDataService:
    """Return the singleton MarketDataService instance."""
    global _market_service
    if _market_service is None:
        with _market_service_lock:
            if _market_service is None:
                _market_service = MarketDataService(cache_ttl_seconds=cache_ttl_seconds)
    return _market_service