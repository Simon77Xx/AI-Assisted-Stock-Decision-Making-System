"""FastAPI backend for backtest data and AI judgement."""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Make backend modules importable (all sibling modules + judgement/ subpackage).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest_engine import (
    check_insufficient_data,
    compute_metrics,
    compute_position_state,
    compute_signals,
    run_backtest,
)
from data_fetcher import get_date_gap_warnings, load_data
from advisor_router import router as advisor_router
from judgement.router import router as ai_judgement_router
from judgement.state import (
    BacktestSnapshot,
    _compute_params_hash,
    update_snapshot,
)

app = FastAPI(title="Stock Backtest API")

app.include_router(ai_judgement_router)
app.include_router(advisor_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BacktestResponse(BaseModel):
    backtestVersion: str
    backtestTimestamp: str
    metrics: dict
    chart_data: list
    signals: list
    currentSignal: str
    dataWarnings: list[str] = []
    snapshot: dict = {}


def serialize_df(df: pd.DataFrame) -> list:
    """Convert a DataFrame to JSON-compatible records."""
    safe_df = df.replace([float("inf"), float("-inf")], pd.NA)
    return json.loads(safe_df.to_json(orient="records", date_format="iso"))


def _compute_current_signal(signals_df: pd.DataFrame) -> str:
    """Return the current mechanical strategy signal."""
    if signals_df.empty:
        return "持有"
    pos = signals_df.iloc[-1].get("position", 0)
    if pos > 0:
        return "买入"
    recent = signals_df[signals_df["position"].diff().fillna(0) != 0]
    if not recent.empty:
        last_signal = recent.iloc[-1]["position"]
        if last_signal > 0:
            return "买入"
        if last_signal < 0:
            return "卖出"
    return "持有"


def _build_data_warnings(
    backtest: pd.DataFrame,
    fast_ma: int,
    slow_ma: int,
    trend_ma: int,
) -> list[str]:
    warnings: list[str] = []
    max_window = max(fast_ma, slow_ma, trend_ma)
    if len(backtest) < max_window:
        warnings.append(
            f"数据不足：历史K线少于 MA{max_window} 窗口，无法计算的指标已标记为空。"
        )
    if backtest[["close", "daily_return", "strategy_return"]].isna().any().any():
        warnings.append("部分行情字段缺失，已在回测前进行清洗。")
    return warnings


def _add_data_source_warnings(
    warnings: list[str],
    original_df: pd.DataFrame,
) -> list[str]:
    """Add data source warnings from stock data (date gaps, suspension)."""
    date_gaps = get_date_gap_warnings(original_df)
    warnings.extend(date_gaps)
    # Check for zero-volume days (potential suspension)
    if "volume" in original_df.columns:
        zero_vol_days = original_df[original_df["volume"].fillna(0) == 0]
        if len(zero_vol_days) > 0:
            zero_pct = len(zero_vol_days) / max(len(original_df), 1) * 100
            if zero_pct > 5:
                warnings.append(f"数据中 {zero_pct:.0f}% 的交易日成交量为 0（可能含停牌日）。")
    return warnings


def _build_snapshot(
    *,
    version_id: str,
    created_at: str,
    stock_code: str,
    params: dict[str, Any],
    signals_df: pd.DataFrame,
    backtest_df: pd.DataFrame,
    original_df: pd.DataFrame,
    metrics: dict,
    current_signal: str,
    warnings: list[str],
) -> BacktestSnapshot:
    """Build a BacktestSnapshot from backtest DataFrames — single source of truth."""
    params_hash = _compute_params_hash(params)
    latest = backtest_df.iloc[-1] if not backtest_df.empty else None

    # MA cross status (computed from signals engine logic)
    ma_cross_status = "无明显交叉"
    cross_date = None
    if signals_df is not None and not signals_df.empty and "MA5" in signals_df.columns and "MA20" in signals_df.columns:
        ma_fast_above_slow = signals_df["MA5"] > signals_df["MA20"]
        cross_changes = ma_fast_above_slow.astype(int).diff().fillna(0)
        golden_indices = signals_df.index[cross_changes == 1]
        death_indices = signals_df.index[cross_changes == -1]
        if len(golden_indices) > 0 and len(death_indices) > 0:
            last_golden = golden_indices[-1]
            last_death = death_indices[-1]
            if last_golden > last_death:
                ma_cross_status = "金叉"
                cross_date = str(signals_df.loc[last_golden, "date"])
            else:
                ma_cross_status = "死叉"
                cross_date = str(signals_df.loc[last_death, "date"])
        elif len(golden_indices) > 0:
            ma_cross_status = "金叉"
            cross_date = str(signals_df.loc[golden_indices[-1], "date"])
        elif len(death_indices) > 0:
            ma_cross_status = "死叉"
            cross_date = str(signals_df.loc[death_indices[-1], "date"])

    # Trend filter
    ma60_val = latest.get("MA60") if latest is not None else None
    close_val = latest.get("close") if latest is not None else None
    trend_up = (
        ma60_val is not None and close_val is not None
        and not pd.isna(ma60_val) and not pd.isna(close_val)
        and float(close_val) > float(ma60_val)
    )
    trend_filter_status = "趋势市" if trend_up else "震荡市"

    # Returns
    return_5d = 0.0
    return_20d = 0.0
    if backtest_df is not None and not backtest_df.empty and "close" in backtest_df.columns:
        closes = backtest_df["close"].values
        if len(closes) >= 5:
            return_5d = (float(closes[-1]) - float(closes[-5])) / float(closes[-5])
        if len(closes) >= 20:
            return_20d = (float(closes[-1]) - float(closes[-20])) / float(closes[-20])

    # Volume ratio
    volume_ratio = 1.0
    if original_df is not None and not original_df.empty and "volume" in original_df.columns:
        volumes = original_df["volume"].values
        latest_vol = float(volumes[-1]) if len(volumes) > 0 else 0
        avg_vol = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else 1.0
        volume_ratio = latest_vol / avg_vol if avg_vol > 0 else 1.0

    # Position state
    pos_state, holding_days = compute_position_state(signals_df)

    # Insufficient data check
    insufficient = check_insufficient_data(signals_df)

    # Max drawdown
    max_dd = None
    if backtest_df is not None and not backtest_df.empty and "strategy_cum" in backtest_df.columns:
        cum_vals = backtest_df["strategy_cum"].replace([np.inf, -np.inf], np.nan).fillna(1).values
        if len(cum_vals) > 0:
            peak = np.maximum.accumulate(cum_vals)
            dd_series = (cum_vals - peak) / peak
            max_dd = float(np.min(dd_series))

    # Trade signals
    trade_signals = []
    if signals_df is not None and not signals_df.empty:
        diffs = signals_df["position"].diff().fillna(0)
        change_points = signals_df[diffs != 0]
        for _, row in change_points.iterrows():
            trade_signals.append({
                "date": str(row["date"]),
                "position": int(row["position"]) if not pd.isna(row["position"]) else 0,
            })

    # Current position text
    current_position_text = "持仓" if pos_state == "LONG" else "空仓"

    return BacktestSnapshot(
        version_id=version_id,
        created_at=created_at,
        stock_code=stock_code,
        params=params,
        params_hash=params_hash,
        current_price=float(latest["close"]) if latest is not None else 0.0,
        ma5=float(latest["MA5"]) if latest is not None and "MA5" in latest and not pd.isna(latest.get("MA5")) else None,
        ma20=float(latest["MA20"]) if latest is not None and "MA20" in latest and not pd.isna(latest.get("MA20")) else None,
        ma60=float(latest["MA60"]) if latest is not None and "MA60" in latest and not pd.isna(latest.get("MA60")) else None,
        ma_cross_status=ma_cross_status,
        cross_date=cross_date,
        trend_filter_status=trend_filter_status,
        return_5d=return_5d,
        return_20d=return_20d,
        volume_ratio=volume_ratio,
        current_position=current_position_text,
        current_signal=current_signal,
        max_drawdown=max_dd,
        position_state=pos_state,
        holding_days=holding_days if holding_days is not None else 0,
        insufficient_data=insufficient["insufficient_data"],
        missing_indicators=insufficient["missing_indicators"],
        signals=trade_signals,
        data_warnings=warnings,
    )


@app.get("/api/backtest")
def run_backtest_api(
    stock_code: str = Query("000001", description="Stock code"),
    start_date: str = Query("2023-01-01", description="Start date YYYY-MM-DD"),
    end_date: str = Query("2024-12-31", description="End date YYYY-MM-DD"),
    fast_ma: int = Query(5, description="Fast MA window"),
    slow_ma: int = Query(20, description="Slow MA window"),
    trend_ma: int = Query(60, description="Trend MA window"),
):
    try:
        df = load_data(stock_code, start_date, end_date)
    except Exception as e:
        return {"error": str(e)}

    if df.empty:
        return {"error": "未获取到数据，请检查股票代码或日期范围"}

    signals = compute_signals(
        df,
        fast_window=fast_ma,
        slow_window=slow_ma,
        trend_window=trend_ma,
    )
    backtest = run_backtest(df, signals)
    metrics = compute_metrics(backtest)

    version = str(uuid.uuid4())[:8]
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    current_signal = _compute_current_signal(signals)
    warnings = _build_data_warnings(backtest, fast_ma, slow_ma, trend_ma)
    warnings = _add_data_source_warnings(warnings, df)

    params = {
        "stock_code": stock_code,
        "start_date": start_date,
        "end_date": end_date,
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
        "trend_ma": trend_ma,
    }

    snapshot = _build_snapshot(
        version_id=version,
        created_at=timestamp,
        stock_code=stock_code,
        params=params,
        signals_df=signals,
        backtest_df=backtest,
        original_df=df,
        metrics=metrics,
        current_signal=current_signal,
        warnings=warnings,
    )

    update_snapshot(snapshot)

    return BacktestResponse(
        backtestVersion=version,
        backtestTimestamp=timestamp,
        currentSignal=current_signal,
        dataWarnings=warnings,
        metrics=metrics,
        chart_data=serialize_df(backtest),
        signals=serialize_df(
            signals[["date", "position"]][signals["position"].diff().fillna(0) != 0]
        ),
        snapshot={
            "current_price": snapshot.current_price,
            "ma5": snapshot.ma5,
            "ma20": snapshot.ma20,
            "ma60": snapshot.ma60,
            "ma_cross_status": snapshot.ma_cross_status,
            "cross_date": snapshot.cross_date or "",
            "trend_filter_status": snapshot.trend_filter_status,
            "return_5d": snapshot.return_5d,
            "return_20d": snapshot.return_20d,
            "volume_ratio": snapshot.volume_ratio,
            "current_position": snapshot.current_position,
            "current_signal": snapshot.current_signal,
            "max_drawdown": snapshot.max_drawdown,
            "position_state": snapshot.position_state,
            "holding_days": snapshot.holding_days,
            "insufficient_data": snapshot.insufficient_data,
            "missing_indicators": snapshot.missing_indicators,
        },
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
