"""Market Data Service — real-time/market data layer for multi-stock analysis.

Provides:
- Real-time stock price fetching via akshare
- Market snapshot with timestamp + stock data map
- TTL-based cache (5 min default)
- Snapshot ID for data version control (prevents stale data usage)

Proxy strategy (for non-China IPs):
  Primary:  Sina (stock_zh_a_spot)  — works through most proxies
  Fallback: EastMoney (stock_zh_a_spot_em) — works through some proxies
  Last:     Sina (stock_zh_a_spot)  — WITHOUT proxy (some ISPs route CN CDNs)
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

import akshare as ak
import pandas as pd

from retry_utils import retry_call, without_proxy

logger = logging.getLogger(__name__)

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

        Strategy (for non-China IPs):
          1. Sina (stock_zh_a_spot) × 3 retries — works through most proxies
          2. EastMoney (stock_zh_a_spot_em) × 2 retries — may work through some
          3. Sina WITHOUT proxy × 1 — last resort
        """

        def _sina() -> pd.DataFrame:
            return ak.stock_zh_a_spot()

        def _em() -> pd.DataFrame:
            return ak.stock_zh_a_spot_em()

        def _sina_no_proxy() -> pd.DataFrame:
            return without_proxy(_sina)

        df = None
        last_error = None

        # Phase 1: Sina (with proxy, 3 retries)
        try:
            df = retry_call(_sina, description="Sina stock_zh_a_spot", retries=3)
        except Exception as e:
            last_error = e
            logger.warning("Sina exhausted retries: %s", e)

        # Phase 2: EastMoney (with proxy, 2 retries) — fallback
        if df is None or df.empty:
            try:
                df = retry_call(_em, description="EastMoney stock_zh_a_spot_em", retries=2)
            except Exception as e:
                last_error = e
                logger.warning("EastMoney also failed: %s", e)

        # Phase 3: Sina without proxy — last resort
        if df is None or df.empty:
            try:
                logger.info("Trying Sina without proxy as last resort...")
                df = _sina_no_proxy()
            except Exception as e:
                last_error = e
                logger.error("All data sources exhausted: %s", e)

        if df is None or df.empty:
            logger.warning("All real-time quote data sources failed, returning empty")
            return {}

        # EastMoney stock_zh_a_spot_em column indices:
        #   [0]=代码(SH/SZ前缀), [1]=名称, [2]=最新价, [3]=涨跌幅(%),
        #   [4]=涨跌额, [5]=成交量(手), [6]=成交额, [7]=振幅,
        #   [8]=最高, [9]=最低, [10]=今开, [11]=昨收
        COL_CODE = 0
        COL_NAME = 1
        COL_PRICE = 2
        COL_CHANGE_PCT = 3
        COL_VOLUME = 5
        COL_AMOUNT = 6
        COL_HIGH = 8
        COL_LOW = 9
        COL_OPEN = 10
        COL_PREV_CLOSE = 11

        # Normalize code column: strip "SH"/"SZ"/"BJ" prefixes
        codes_raw = df.iloc[:, COL_CODE].astype(str).str.strip()
        codes_clean = codes_raw.str.replace(r'^(SH|SZ|BJ|sh|sz|bj)', '', case=False, regex=True)

        # Build a lookup: clean_code -> row index
        code_to_idx = {}
        seen_codes = set()
        for i, clean_code in enumerate(codes_clean):
            if clean_code in seen_codes:
                continue
            seen_codes.add(clean_code)
            code_to_idx[clean_code] = i

        quotes: dict[str, StockRealtimeQuote] = {}
        for target_code in stock_codes:
            target_clean = target_code.strip()
            row_idx = code_to_idx.get(target_clean)
            if row_idx is None:
                continue

            row = df.iloc[row_idx]
            code = str(row.iloc[COL_CODE]).strip()
            name = str(row.iloc[COL_NAME])
            try:
                price = float(row.iloc[COL_PRICE] or 0)
                change_pct_val = float(row.iloc[COL_CHANGE_PCT] or 0) / 100.0
                volume = float(row.iloc[COL_VOLUME] or 0)
                amount = float(row.iloc[COL_AMOUNT] or 0)

                high = float(row.iloc[COL_HIGH]) if pd.notna(row.iloc[COL_HIGH]) else None
                low = float(row.iloc[COL_LOW]) if pd.notna(row.iloc[COL_LOW]) else None
                open_ = float(row.iloc[COL_OPEN]) if pd.notna(row.iloc[COL_OPEN]) else None
                prev_close = float(row.iloc[COL_PREV_CLOSE]) if pd.notna(row.iloc[COL_PREV_CLOSE]) else None

                quote = StockRealtimeQuote(
                    stock_code=target_code,
                    stock_name=name,
                    price=price,
                    change_pct=change_pct_val,
                    volume=volume,
                    amount=amount,
                    turnover=None,
                    high=high,
                    low=low,
                    open_=open_,
                    prev_close=prev_close,
                )
                quotes[target_code] = quote
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