"""Financial Data Analyzer — fundamental analysis using akshare.

Fetches and analyzes key financial metrics for A-share stocks:
  - Profitability: ROE, net profit margin, gross margin
  - Valuation: PE_TTM, PB ratio
  - Growth: revenue YoY growth, net profit YoY growth
  - Health: debt ratio, current ratio

All data cached by stock code with configurable TTL.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional

import akshare as ak
import pandas as pd

from retry_utils import retry_call

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour (financial data changes slowly)

# ── Column name mappings ──────────────────────────────────────────────
# stock_financial_abstract_ths returns Chinese column names
COL_REPORT_DATE = "\u62a5\u544a\u671f"  # 报告期
COL_NET_PROFIT = "\u51c0\u5229\u6da6"  # 净利润
COL_NET_PROFIT_GROWTH = "\u51c0\u5229\u6da6\u540c\u6bd4\u589e\u957f\u7387"  # 净利润同比增长率
COL_REVENUE = "\u8425\u4e1a\u603b\u6536\u5165"  # 营业总收入
COL_REVENUE_GROWTH = "\u8425\u4e1a\u603b\u6536\u5165\u540c\u6bd4\u589e\u957f\u7387"  # 营业总收入同比增长率
COL_EPS = "\u57fa\u672c\u6bcf\u80a1\u6536\u76ca"  # 基本每股收益
COL_BVPS = "\u6bcf\u80a1\u51c0\u8d44\u4ea7"  # 每股净资产
COL_NET_PROFIT_MARGIN = "\u9500\u552e\u51c0\u5229\u7387"  # 销售净利率
COL_GROSS_MARGIN = "\u9500\u552e\u6bdb\u5229\u7387"  # 销售毛利率
COL_ROE = "\u51c0\u8d44\u4ea7\u6536\u76ca\u7387"  # 净资产收益率
COL_DEBT_RATIO = "\u8d44\u4ea7\u8d1f\u503a\u7387"  # 资产负债率
COL_CURRENT_RATIO = "\u6d41\u52a8\u6bd4\u7387"  # 流动比率


@dataclass(frozen=True)
class FinancialMetrics:
    """Key financial metrics for a single stock (most recent reporting period)."""
    stock_code: str
    stock_name: str = ""

    # Profitability
    roe: Optional[float] = None          # 净资产收益率 %
    net_profit_margin: Optional[float] = None  # 销售净利率 %
    gross_margin: Optional[float] = None       # 销售毛利率 %

    # Valuation
    pe_ttm: Optional[float] = None       # 滚动市盈率
    pb: Optional[float] = None           # 市净率

    # Growth (YoY)
    revenue_growth: Optional[float] = None     # 营收同比增长率 %
    net_profit_growth: Optional[float] = None  # 净利润同比增长率 %

    # Health
    debt_ratio: Optional[float] = None   # 资产负债率 %
    current_ratio: Optional[float] = None  # 流动比率

    # Per share
    eps: Optional[float] = None          # 基本每股收益
    bvps: Optional[float] = None         # 每股净资产

    # Raw data
    report_date: str = ""
    source: str = "akshare"
    fetch_time: str = ""

    @property
    def has_data(self) -> bool:
        return any(v is not None for v in [
            self.roe, self.pe_ttm, self.revenue_growth, self.net_profit_growth
        ])


def _parse_pct(val: Any) -> Optional[float]:
    """Parse a percentage value from akshare (may be '1.23亿', '23.45%', False, etc.)."""
    if val is None or val is False or val is True:
        return None
    try:
        s = str(val).strip()
        if not s or s == "False" or s == "True":
            return None
        # Remove percentage sign
        s = s.replace("%", "").replace("％", "")
        # Handle "亿" (hundred million) units
        if "\u4ebf" in s:
            return float(s.replace("\u4ebf", "").strip())
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_str_val(val: Any) -> Optional[str]:
    """Get string value or None."""
    if val is None or val is False:
        return None
    s = str(val).strip()
    if not s or s == "False" or s == "True":
        return None
    return s


# ---------------------------------------------------------------------------
# Financial data fetching
# ---------------------------------------------------------------------------

_FIN_CACHE: dict[str, tuple[FinancialMetrics, float]] = {}
_FIN_CACHE_LOCK = Lock()


def _cache_key(stock_code: str) -> str:
    return f"fin:{stock_code}"


def _get_cached(stock_code: str) -> Optional[FinancialMetrics]:
    now = time.time()
    with _FIN_CACHE_LOCK:
        entry = _FIN_CACHE.get(_cache_key(stock_code))
        if entry and (now - entry[1]) < CACHE_TTL:
            return entry[0]
    return None


def _store_cache(stock_code: str, metrics: FinancialMetrics) -> None:
    with _FIN_CACHE_LOCK:
        _FIN_CACHE[_cache_key(stock_code)] = (metrics, time.time())


def get_financial_metrics(
    stock_code: str,
    stock_name: str = "",
    force_refresh: bool = False,
) -> FinancialMetrics:
    """Fetch financial metrics for a stock.

    Uses cache (1 hour TTL). Returns FinancialMetrics — check .has_data
    to see if data was actually fetched.
    """
    if not force_refresh:
        cached = _get_cached(stock_code)
        if cached is not None:
            return cached

    metrics = _fetch_financial_metrics(stock_code, stock_name)
    _store_cache(stock_code, metrics)
    return metrics


def _fetch_financial_metrics(stock_code: str, stock_name: str) -> FinancialMetrics:
    """Actually fetch financial data from akshare."""
    from datetime import datetime, timezone

    fetch_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 1. Financial abstract (THS — balance sheet / income statement metrics)
    fin_data = _fetch_financial_abstract(stock_code)

    # 2. PE/PB data
    pe_data = _fetch_pe_pb_data(stock_code)

    # Merge
    kwargs: dict[str, Any] = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "fetch_time": fetch_time,
        "source": "akshare",
    }

    if fin_data:
        kwargs.update(fin_data)
    if pe_data:
        kwargs.update(pe_data)

    return FinancialMetrics(**{k: v for k, v in kwargs.items() if hasattr(FinancialMetrics, k)})


def _fetch_financial_abstract(stock_code: str) -> Optional[dict[str, Any]]:
    """Fetch financial abstract from 同花顺 via akshare.

    Returns dict with keys matching FinancialMetrics fields.
    """
    try:
        df = retry_call(
            lambda: ak.stock_financial_abstract_ths(symbol=stock_code),
            description=f"Financial abstract {stock_code}",
            retries=2,
        )
    except Exception as e:
        logger.warning("Failed to fetch financial abstract for %s: %s", stock_code, e)
        return None

    if df is None or df.empty:
        return None

    # Most recent period (first row)
    row = df.iloc[0]
    result: dict[str, Any] = {}

    # Parse each field
    result["report_date"] = _parse_str_val(row.get(COL_REPORT_DATE)) or ""

    roe = _parse_pct(row.get(COL_ROE))
    if roe is not None:
        result["roe"] = roe

    margin = _parse_pct(row.get(COL_NET_PROFIT_MARGIN))
    if margin is not None:
        result["net_profit_margin"] = margin

    gross = _parse_pct(row.get(COL_GROSS_MARGIN))
    if gross is not None:
        result["gross_margin"] = gross

    rev_growth = _parse_pct(row.get(COL_REVENUE_GROWTH))
    if rev_growth is not None:
        result["revenue_growth"] = rev_growth

    profit_growth = _parse_pct(row.get(COL_NET_PROFIT_GROWTH))
    if profit_growth is not None:
        result["net_profit_growth"] = profit_growth

    debt = _parse_pct(row.get(COL_DEBT_RATIO))
    if debt is not None:
        result["debt_ratio"] = debt

    cr = _parse_pct(row.get(COL_CURRENT_RATIO))
    if cr is not None:
        result["current_ratio"] = cr

    eps = _parse_pct(row.get(COL_EPS))
    if eps is not None:
        result["eps"] = eps

    bvps = _parse_pct(row.get(COL_BVPS))
    if bvps is not None:
        result["bvps"] = bvps

    return result


def _fetch_pe_pb_data(stock_code: str) -> Optional[dict[str, Any]]:
    """Fetch PE/PB data for a stock.

    Uses stock_a_ttm_lyr which returns PE_TTM values for all stocks.
    Falls back to returning None if unavailable.
    """
    try:
        # stock_a_ttm_lyr returns PE data for all A shares on a given date
        # We need the latest snapshot, filter by stock code
        df = retry_call(
            lambda: ak.stock_a_ttm_lyr(),
            description=f"PE/PB data (all stocks)",
            retries=2,
        )
    except Exception as e:
        logger.warning("Failed to fetch PE/PB data: %s", e)
        return None

    if df is None or df.empty:
        return None

    # The data has columns: date, middlePETTM, averagePETTM, ...
    # stock_a_ttm_lyr does not have stock codes directly — it's market-wide.
    # Instead we use a simpler approach: just get the latest TTM PE for the
    # overall market as a reference, or return None for individual PE.
    #
    # For individual stock PE, we try stock_financial_analysis_indicator
    return _fetch_pe_from_indicator(stock_code)


def _fetch_pe_from_indicator(stock_code: str) -> Optional[dict[str, Any]]:
    """Fetch PE/PB from financial analysis indicator."""
    try:
        df = retry_call(
            lambda: ak.stock_financial_analysis_indicator(symbol=stock_code, start_year="2024"),
            description=f"Fin indicator {stock_code}",
            retries=1,
        )
    except Exception as e:
        logger.debug("Fin indicator PE/PB unavailable: %s", e)
        return None

    if df is None or df.empty:
        return None

    result: dict[str, Any] = {}
    # The columns are Chinese; try to find PE and PB related columns
    for col in df.columns:
        col_str = str(col)
        # Look for PE-related columns
        if "\u5e02\u76c8\u7387" in col_str or "PE" in col_str.upper():
            val = _parse_pct(df.iloc[0].get(col))
            if val is not None:
                result["pe_ttm"] = val
        # Look for PB-related columns
        if "\u5e02\u51c0\u7387" in col_str or "PB" in col_str.upper():
            val = _parse_pct(df.iloc[0].get(col))
            if val is not None:
                result["pb"] = val

    return result if result else None


def invalidate_cache(stock_code: str) -> None:
    """Clear cached financial data for a stock."""
    with _FIN_CACHE_LOCK:
        _FIN_CACHE.pop(_cache_key(stock_code), None)


def invalidate_all_cache() -> None:
    """Clear all cached financial data."""
    with _FIN_CACHE_LOCK:
        _FIN_CACHE.clear()