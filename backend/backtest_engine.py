"""Backtest engine for the dual moving-average strategy."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _clean_numeric_frame(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for col in ["open", "close", "high", "low", "volume"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    result = result.replace([np.inf, -np.inf], np.nan)
    if "close" in result.columns:
        result["close"] = result["close"].ffill().bfill()
    return result


def compute_signals(
    df: pd.DataFrame,
    fast_window: int = 5,
    slow_window: int = 20,
    trend_window: int = 60,
) -> pd.DataFrame:
    """Compute MA signals. Insufficient MA windows stay null and produce no trades."""
    clean_df = _clean_numeric_frame(df)
    result = clean_df[["date", "close"]].copy()

    result["MA5"] = clean_df["close"].rolling(window=fast_window, min_periods=fast_window).mean()
    result["MA20"] = clean_df["close"].rolling(window=slow_window, min_periods=slow_window).mean()
    result["MA60"] = clean_df["close"].rolling(window=trend_window, min_periods=trend_window).mean()

    ready_mask = result[["MA5", "MA20", "MA60", "close"]].notna().all(axis=1)

    result["trend_up"] = False
    result.loc[ready_mask, "trend_up"] = (
        result.loc[ready_mask, "close"] > result.loc[ready_mask, "MA60"]
    )

    ma_fast_above_slow = result["MA5"] > result["MA20"]
    result["raw_signal"] = 0

    golden_cross = ma_fast_above_slow & ~ma_fast_above_slow.shift(1).fillna(False)
    result.loc[golden_cross & result["trend_up"] & ready_mask, "raw_signal"] = 1

    death_cross = ~ma_fast_above_slow & ma_fast_above_slow.shift(1).fillna(False)
    result.loc[death_cross & ready_mask, "raw_signal"] = -1

    trend_end = ~result["trend_up"] & result["trend_up"].shift(1).fillna(False)
    result.loc[trend_end & ready_mask, "raw_signal"] = -1

    result["signal"] = result["raw_signal"].shift(1).fillna(0)
    result["position"] = result["signal"].replace(0, np.nan).ffill().fillna(0)
    result["position"] = result["position"].where(ready_mask | (result["position"] == 0), 0)
    return result.replace([np.inf, -np.inf], np.nan)


def compute_position_state(signals_df: pd.DataFrame) -> tuple[str, int]:
    """Determine current position state and consecutive holding days.

    Returns:
        (state_name, holding_days)
        state_name is 'FLAT' or 'LONG'.
        holding_days counts consecutive days in the current position.
    """
    if signals_df.empty or "position" not in signals_df.columns:
        return ("FLAT", 0)

    last_position = signals_df["position"].iloc[-1]
    last_position = 0 if pd.isna(last_position) else int(last_position)
    state = "LONG" if last_position > 0 else "FLAT"

    holding_days = 0
    for i in range(len(signals_df) - 1, -1, -1):
        pos = signals_df["position"].iloc[i]
        if pd.isna(pos):
            break
        if int(pos) == last_position:
            holding_days += 1
        else:
            break

    return (state, holding_days)


def check_insufficient_data(signals_df: pd.DataFrame) -> dict:
    """Check if the signals DataFrame has insufficient MA data (e.g., 次新股).

    Returns:
        {"insufficient_data": bool, "missing_indicators": list[str]}
    """
    result = {"insufficient_data": False, "missing_indicators": []}
    if signals_df.empty:
        return result

    last = signals_df.iloc[-1]
    for ma_col in ["MA5", "MA20", "MA60"]:
        if ma_col in signals_df.columns and pd.isna(last.get(ma_col)):
            result["missing_indicators"].append(ma_col)

    if result["missing_indicators"]:
        result["insufficient_data"] = True
    return result


def run_backtest(df: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    """Run backtest and sanitize returns for suspended/abnormal data."""
    clean_df = _clean_numeric_frame(df)
    result = signals[["date", "close", "MA5", "MA20", "MA60", "position"]].copy()

    result["daily_return"] = clean_df["close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0)
    result["strategy_return"] = result["daily_return"] * result["position"].shift(1).fillna(0)
    result["strategy_return"] = result["strategy_return"].replace([np.inf, -np.inf], np.nan).fillna(0)

    result["strategy_cum"] = (1 + result["strategy_return"]).cumprod()
    result["benchmark_cum"] = (1 + result["daily_return"]).cumprod()
    return result.replace([np.inf, -np.inf], np.nan)


def _fmt_pct(value: float) -> str:
    value = 0.0 if pd.isna(value) or np.isinf(value) else float(value)
    return f"{value:.2%}"


def compute_metrics(backtest_result: pd.DataFrame) -> dict:
    """Compute performance metrics with empty/NaN-safe fallbacks."""
    if backtest_result.empty:
        return {
            "累计收益率": "0.00%",
            "买入持有收益率": "0.00%",
            "年化收益率": "0.00%",
            "买入持有年化收益率": "0.00%",
            "最大回撤": "0.00%",
            "买入持有最大回撤": "0.00%",
            "夏普比率": "0.00",
            "胜率": "0.00%",
            "交易次数": 0,
        }

    sr = backtest_result["strategy_return"].replace([np.inf, -np.inf], np.nan).fillna(0)
    cum_return = backtest_result["strategy_cum"].fillna(1).iloc[-1] - 1
    benchmark_cum_return = backtest_result["benchmark_cum"].fillna(1).iloc[-1] - 1

    n_days = max(len(sr), 1)
    annual_return = (1 + cum_return) ** (244 / n_days) - 1 if (1 + cum_return) > 0 else -1
    benchmark_annual_return = (
        (1 + benchmark_cum_return) ** (244 / n_days) - 1
        if (1 + benchmark_cum_return) > 0
        else -1
    )

    cum = backtest_result["strategy_cum"].replace([np.inf, -np.inf], np.nan).fillna(1)
    rolling_max = cum.cummax().replace(0, np.nan)
    max_drawdown = ((cum - rolling_max) / rolling_max).fillna(0).min()

    benchmark_cum = backtest_result["benchmark_cum"].replace([np.inf, -np.inf], np.nan).fillna(1)
    benchmark_rolling_max = benchmark_cum.cummax().replace(0, np.nan)
    benchmark_max_drawdown = ((benchmark_cum - benchmark_rolling_max) / benchmark_rolling_max).fillna(0).min()

    risk_free = 0.02
    excess_returns = sr - risk_free / 244
    sr_std = sr.std()
    sharpe = np.sqrt(244) * excess_returns.mean() / sr_std if sr_std and not pd.isna(sr_std) else 0.0

    trade_returns = sr[sr != 0]
    win_rate = (trade_returns > 0).sum() / len(trade_returns) if len(trade_returns) > 0 else 0
    position_changes = (backtest_result["position"].diff().fillna(0) != 0).sum()
    trade_count = int(position_changes // 2)

    return {
        "累计收益率": _fmt_pct(cum_return),
        "买入持有收益率": _fmt_pct(benchmark_cum_return),
        "年化收益率": _fmt_pct(annual_return),
        "买入持有年化收益率": _fmt_pct(benchmark_annual_return),
        "最大回撤": _fmt_pct(max_drawdown),
        "买入持有最大回撤": _fmt_pct(benchmark_max_drawdown),
        "夏普比率": f"{0.0 if pd.isna(sharpe) or np.isinf(sharpe) else sharpe:.2f}",
        "胜率": _fmt_pct(win_rate),
        "交易次数": trade_count,
    }


if __name__ == "__main__":
    from data_fetcher import load_data

    df = load_data("000001", "2023-01-01", "2024-12-31")
    signals = compute_signals(df)
    backtest = run_backtest(df, signals)
    metrics = compute_metrics(backtest)
    for key, value in metrics.items():
        print(f"{key}: {value}")
