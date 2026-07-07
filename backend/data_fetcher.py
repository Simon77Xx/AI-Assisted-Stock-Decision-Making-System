"""Stock data fetcher with trading-day based parquet cache."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import akshare as ak
import numpy as np
import pandas as pd

from retry_utils import retry_call, without_proxy

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

REQUIRED_COLUMNS = ["date", "open", "close", "high", "low", "volume"]
NUMERIC_COLUMNS = [
    "open",
    "close",
    "high",
    "low",
    "volume",
    "amount",
    "amplitude",
    "pct_change",
    "change",
    "turnover",
]


def _cache_path(stock_code: str) -> Path:
    return CACHE_DIR / f"{stock_code}.parquet"


def _meta_path(stock_code: str) -> Path:
    return CACHE_DIR / f"{stock_code}.meta.json"


def _read_meta(stock_code: str) -> dict[str, Any]:
    path = _meta_path(stock_code)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_meta(stock_code: str, df: pd.DataFrame) -> None:
    last_trading_date = None
    if not df.empty and "date" in df.columns:
        last_trading_date = pd.to_datetime(df["date"]).max().strftime("%Y-%m-%d")
    _meta_path(stock_code).write_text(
        json.dumps({"lastTradingDate": last_trading_date}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Check if columns are Chinese (EastMoney style) or English (Sina style)
    chinese_cols = {"日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low"}
    has_chinese = any(col in df.columns for col in chinese_cols)

    if has_chinese:
        df = df.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "振幅": "amplitude",
                "涨跌幅": "pct_change",
                "涨跌额": "change",
                "换手率": "turnover",
            }
        )

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"AkShare返回数据缺少必要字段: {', '.join(missing)}")
    return df


def _detect_date_gaps(df: pd.DataFrame) -> list[str]:
    """Detect gaps in trading dates > 5 business days."""
    warnings: list[str] = []
    if df.empty or "date" not in df.columns:
        return warnings
    dates = df["date"].dropna().sort_values()
    if len(dates) < 2:
        return warnings
    gaps = dates.diff().dt.days.dropna()
    large_gaps = gaps[gaps > 5]
    for idx in large_gaps.index:
        prev_date = str(dates.loc[:idx].iloc[-2].date()) if len(dates.loc[:idx]) >= 2 else "unknown"
        next_date = str(dates.loc[idx].date())
        gap_days = int(gaps.loc[idx])
        warnings.append(f"数据断层：{prev_date} 至 {next_date} 间隔 {gap_days} 天（可能停牌）")
    return warnings


def get_date_gap_warnings(df: pd.DataFrame) -> list[str]:
    """Detect gaps in trading dates > 5 business days. Public wrapper."""
    return _detect_date_gaps(df)


def _clean_market_data(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalize_columns(df.copy())
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date")
    if "volume" in df.columns:
        df["volume"] = df["volume"].fillna(0)
    for col in ["open", "high", "low"]:
        if col in df.columns:
            df[col] = df[col].fillna(df["close"])
    return df.reset_index(drop=True)


def _fetch_from_akshare(stock_code: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
    """Fetch historical data with Sina primary + EastMoney/proxy-bypass fallback."""
    code = stock_code.lstrip("sh").lstrip("sz").lstrip("SH").lstrip("SZ").lstrip("bj").lstrip("BJ")

    # Sina needs sh/sz prefix
    sina_code = f"sh{code}" if code.startswith(("6", "688")) else f"sz{code}"

    def _sina() -> pd.DataFrame:
        return ak.stock_zh_a_daily(symbol=sina_code, adjust="qfq")

    def _em() -> pd.DataFrame:
        return ak.stock_zh_a_hist_em(symbol=code, start_date=start_date or "1970-01-01", end_date=end_date, adjust="qfq")

    df = None

    # Phase 1: Sina (with proxy, 2 retries)
    try:
        df = retry_call(_sina, description=f"Sina {code}", retries=2, base_delay=5.0)
    except Exception as e:
        logger.warning("Sina historical data failed for %s: %s", code, e)

    # Phase 2: EastMoney (with proxy, 2 retries) — fallback
    if df is None or df.empty:
        try:
            df = retry_call(_em, description=f"EastMoney {code}", retries=2, base_delay=5.0)
        except Exception as e:
            logger.warning("EastMoney historical data failed for %s: %s", code, e)

    # Phase 3: Sina without proxy — last resort
    if df is None or df.empty:
        try:
            logger.info("Trying Sina %s without proxy...", code)
            df = without_proxy(_sina)
        except Exception as e:
            raise RuntimeError(f"获取股票 {code} 数据失败（已尝试 Sina/EastMoney/去代理）: {e}") from e

    if df is None or df.empty:
        raise ValueError(f"未获取到股票 {code} 的数据，请检查股票代码是否正确")
    return _clean_market_data(df)


def _fetch_latest_trading_date(stock_code: str, end_date: str) -> pd.Timestamp | None:
    end_ts = pd.Timestamp(end_date)
    start_ts = end_ts - pd.Timedelta(days=45)
    try:
        latest_df = _fetch_from_akshare(
            stock_code,
            start_ts.strftime("%Y-%m-%d"),
            end_ts.strftime("%Y-%m-%d"),
        )
    except Exception:
        return None
    if latest_df.empty:
        return None
    return pd.to_datetime(latest_df["date"]).max()


def _slice_range(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    return df[(df["date"] >= start_ts) & (df["date"] <= end_ts)].reset_index(drop=True)


def _cache_is_usable(
    df: pd.DataFrame,
    stock_code: str,
    start_date: str,
    end_date: str,
) -> bool:
    if df.empty or df["date"].min() > pd.Timestamp(start_date):
        return False

    requested_end = pd.Timestamp(end_date)
    cache_last = pd.to_datetime(df["date"]).max()
    if cache_last >= requested_end:
        return True

    latest_trading_date = _fetch_latest_trading_date(stock_code, end_date)
    if latest_trading_date is None:
        return False

    meta_last = _read_meta(stock_code).get("lastTradingDate")
    same_trading_day = cache_last.normalize() == latest_trading_date.normalize()
    same_meta = meta_last == latest_trading_date.strftime("%Y-%m-%d")
    return same_trading_day and same_meta


def load_data(stock_code: str, start_date: str, end_date: str, force_refresh: bool = False) -> pd.DataFrame:
    """Load stock data using cache validity driven by last trading date."""
    cache_file = _cache_path(stock_code)

    if not force_refresh and cache_file.exists():
        cached_df = _clean_market_data(pd.read_parquet(cache_file))
        if _cache_is_usable(cached_df, stock_code, start_date, end_date):
            sliced = _slice_range(cached_df, start_date, end_date)
            if not sliced.empty:
                return sliced

    df = _fetch_from_akshare(stock_code, start_date, end_date)
    df.to_parquet(cache_file, index=False)
    _write_meta(stock_code, df)
    return df


if __name__ == "__main__":
    sample = load_data("000001", "2023-01-01", "2024-12-31")
    print(sample.head())
    print(f"Data range: {sample['date'].min()} ~ {sample['date'].max()}")
    print(f"Rows: {len(sample)}")
