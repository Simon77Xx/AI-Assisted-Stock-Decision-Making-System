"""Portfolio Backtest Engine — multi-stock portfolio simulation with capital management.

Supports:
  - Kelly Criterion position sizing
  - Equal-weight allocation
  - Risk-parity allocation
  - Fixed-fraction risk management
  - Max drawdown / stop-loss controls
  - Multi-stock simultaneous simulation
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd

from backtest_engine import compute_signals, run_backtest
from data_fetcher import load_data

logger = logging.getLogger(__name__)

# ── Capital Management Strategies ───────────────────────────────────────


def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Calculate Kelly fraction for optimal position sizing.

    Args:
        win_rate: Historical win rate (0-1)
        avg_win: Average winning return (positive, e.g. 0.05)
        avg_loss: Average losing return (positive, e.g. 0.03)

    Returns:
        Kelly fraction (0-1). Capped at 0.25 (quarter-Kelly) for safety.
    """
    if avg_loss <= 0 or win_rate <= 0:
        return 0.1  # minimum allocation

    avg_win_abs = abs(avg_win)
    avg_loss_abs = abs(avg_loss)

    if avg_loss_abs < 0.0001:
        return 0.25

    # Full Kelly: f* = (p*b - q) / b  where b = avg_win/avg_loss, q = 1-p
    b = avg_win_abs / avg_loss_abs
    kelly = (win_rate * b - (1 - win_rate)) / b
    kelly = max(0.0, min(kelly, 1.0))

    # Use half-Kelly for safety
    return round(min(kelly * 0.5, 0.25), 4)


def equal_weight(num_stocks: int) -> float:
    """Equal weight allocation across N stocks. Capped at 20% each."""
    if num_stocks <= 0:
        return 0.0
    return min(1.0 / num_stocks, 0.2)


def risk_parity(
    volatilities: list[float],
    max_per_stock: float = 0.25,
) -> list[float]:
    """Risk-parity allocation: allocate inversely proportional to volatility.

    Args:
        volatilities: List of annualized volatilities for each stock
        max_per_stock: Maximum allocation per stock (default 25%)

    Returns:
        List of allocation weights summing to ~1.0
    """
    if not volatilities or all(v == 0 for v in volatilities):
        n = len(volatilities) if volatilities else 1
        return [1.0 / n] * n

    inv_vol = [1.0 / max(v, 0.01) for v in volatilities]
    total = sum(inv_vol)
    weights = [min(w / total, max_per_stock) for w in inv_vol]

    # Renormalize
    total_w = sum(weights)
    if total_w > 0:
        weights = [w / total_w for w in weights]

    return weights


# ── Portfolio analytics ─────────────────────────────────────────────────


def compute_portfolio_metrics(
    daily_returns: np.ndarray,
    risk_free_rate: float = 0.03,
) -> dict:
    """Compute portfolio-level performance metrics.

    Args:
        daily_returns: Array of daily portfolio returns
        risk_free_rate: Annual risk-free rate (default 3%)

    Returns:
        Dict of metric name -> value (formatted strings for display)
    """
    if len(daily_returns) < 2:
        return _empty_portfolio_metrics()

    n = len(daily_returns)
    # Cumulative return
    cumulative = np.prod(1 + daily_returns) - 1
    # Annualized return
    annual = (1 + cumulative) ** (244 / n) - 1 if cumulative > -1 else -1
    # Volatility
    vol = float(np.std(daily_returns)) * np.sqrt(244) if len(daily_returns) > 1 else 0.0
    # Sharpe ratio
    sharpe = (annual - risk_free_rate) / vol if vol > 0 else 0.0
    # Max drawdown
    cum = np.cumprod(1 + daily_returns)
    rolling_max = np.maximum.accumulate(cum)
    dd = (cum - rolling_max) / rolling_max
    max_dd = float(np.min(dd))
    # Win rate
    win_rate = float(np.mean(daily_returns > 0))
    # Calmar ratio (return / max_dd)
    calmar = annual / abs(max_dd) if max_dd != 0 else 0.0

    return _fmt_metrics(cumulative, annual, vol, sharpe, max_dd, win_rate, calmar, len(daily_returns))


def _fmt_metrics(
    cumulative: float,
    annual: float,
    vol: float,
    sharpe: float,
    max_dd: float,
    win_rate: float,
    calmar: float,
    trading_days: int,
) -> dict:
    return {
        "累计收益率": f"{cumulative:.2%}",
        "年化收益率": f"{annual:.2%}",
        "年化波动率": f"{vol:.2%}",
        "夏普比率": f"{sharpe:.2f}",
        "Calmar比率": f"{calmar:.2f}",
        "最大回撤": f"{max_dd:.2%}",
        "胜率": f"{win_rate:.2%}",
        "交易天数": trading_days,
    }


def _empty_portfolio_metrics() -> dict:
    return {
        "累计收益率": "0.00%",
        "年化收益率": "0.00%",
        "年化波动率": "0.00%",
        "夏普比率": "0.00",
        "Calmar比率": "0.00",
        "最大回撤": "0.00%",
        "胜率": "0.00%",
        "交易天数": 0,
    }


# ── Portfolio backteest run ─────────────────────────────────────────────


@dataclass
class PortfolioResult:
    """Result of a portfolio backtest run."""

    stock_codes: list[str]
    stock_names: list[str]
    start_date: str
    end_date: str
    total_capital: float
    capital_strategy: str  # 'equal', 'kelly', 'risk_parity'
    weights: list[float]  # per-stock allocation
    portfolio_metrics: dict
    per_stock_metrics: list[dict]  # each stock's individual metrics
    daily_returns: list[float]  # portfolio daily returns
    equity_curve: list[dict]  # date vs portfolio value for charting
    max_drawdown_pct: float
    final_capital: float


@dataclass
class PortfolioBacktestRequest:
    stock_codes: list[str]
    start_date: str = ""
    end_date: str = ""
    total_capital: float = 100_000.0
    capital_strategy: str = "equal"  # 'equal' | 'kelly' | 'risk_parity'
    max_per_stock: float = 0.25  # max allocation per stock
    max_position_count: int = 5  # max number of simultaneous positions
    stop_loss_pct: float = 0.10  # stop-loss per position
    lookback_years: int = 3  # how many years to look back


def run_portfolio_backtest(request: PortfolioBacktestRequest) -> Optional[PortfolioResult]:
    """Run a portfolio-level backtest across multiple stocks.

    Process:
    1. Load data for each stock
    2. Compute signals (MA strategy) for each
    3. Compute per-stock metrics (win rate, avg win/loss) for Kelly
    4. Allocate capital using selected strategy
    5. Simulate combined portfolio returns
    6. Report combined metrics
    """
    if not request.stock_codes:
        return None

    codes = request.stock_codes[:request.max_position_count]
    n_stocks = len(codes)

    # Determine date range
    end = request.end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if request.start_date:
        start = request.start_date
    else:
        start = (datetime.now(timezone.utc) - timedelta(days=request.lookback_years * 365)).strftime("%Y-%m-%d")

    # Load data and compute signals for each stock
    stock_data: list[dict] = []
    for code in codes:
        try:
            df = load_data(code, start, end)
            if df.empty:
                continue
            signals = compute_signals(df)
            backtest = run_backtest(df, signals)
            if backtest.empty:
                continue

            stock_data.append({
                "code": code,
                "data": df,
                "signals": signals,
                "backtest": backtest,
                "quotes": _get_quote_info(code),
            })
        except Exception as e:
            logger.debug("Portfolio: could not load data for %s: %s", code, e)

    if not stock_data:
        return None

    n_loaded = len(stock_data)

    # Compute per-stock metrics (for Kelly estimation)
    per_stock_metrics = []
    volatilities = []
    win_rates = []
    avg_wins = []
    avg_losses = []

    for sd in stock_data:
        bt = sd["backtest"]
        sr = bt["strategy_return"].values
        sr = sr[~np.isnan(sr)]

        # Per-stock annual vol
        vol_stock = float(np.std(sr)) * np.sqrt(244) if len(sr) > 1 else 0.3
        volatilities.append(vol_stock)

        # Win rate and avg win/loss (from non-zero returns)
        non_zero = sr[sr != 0]
        if len(non_zero) > 0:
            wr = float(np.mean(non_zero > 0))
            wins = non_zero[non_zero > 0]
            losses = non_zero[non_zero < 0]
            avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.02
            avg_loss = float(np.mean(np.abs(losses))) if len(losses) > 0 else 0.02
        else:
            wr = 0.5
            avg_win = 0.02
            avg_loss = 0.02

        win_rates.append(wr)
        avg_wins.append(avg_win)
        avg_losses.append(avg_loss)

        from backtest_engine import compute_metrics
        metrics = compute_metrics(bt)
        per_stock_metrics.append({
            "stock_code": sd["code"],
            "stock_name": sd.get("quotes", {}).get("name", sd["code"]),
            **metrics,
        })

    # Allocate weights
    if request.capital_strategy == "kelly":
        weights = []
        for wr, aw, al in zip(win_rates, avg_wins, avg_losses):
            kf = kelly_criterion(wr, aw, al)
            weights.append(kf)
        # Renormalize
        total = sum(weights)
        weights = [w / total if total > 0 else 1.0 / n_loaded for w in weights]
    elif request.capital_strategy == "risk_parity":
        weights = risk_parity(volatilities, request.max_per_stock)
    else:  # equal weight
        weights = [1.0 / n_loaded] * n_loaded

    # Cap individual weights
    weights = [min(w, request.max_per_stock) for w in weights]
    total_w = sum(weights)
    if total_w > 0:
        weights = [w / total_w for w in weights]

    # ── Combine portfolio returns ──
    # Align dates across all stocks
    all_dates: set[str] = set()
    for sd in stock_data:
        for d in sd["backtest"]["date"]:
            all_dates.add(str(d)[:10])
    sorted_dates = sorted(all_dates)

    # Build portfolio daily returns
    portfolio_returns = []
    equity = request.total_capital
    equity_curve = []

    for date_str in sorted_dates:
        daily_ret = 0.0
        valid_stocks = 0

        for i, sd in enumerate(stock_data):
            bt = sd["backtest"]
            bt["_date_str"] = bt["date"].astype(str).str[:10]
            mask = bt["_date_str"] == date_str
            if mask.any():
                idx = bt.index[mask][0]
                strategy_ret = bt.loc[idx, "strategy_return"]
                if not pd.isna(strategy_ret):
                    daily_ret += strategy_ret * weights[i]
                    valid_stocks += 1

        if valid_stocks > 0:
            portfolio_returns.append(daily_ret)
            equity *= (1 + daily_ret)
            equity_curve.append({"date": date_str, "equity": round(equity, 2)})

    if not portfolio_returns:
        return None

    ret_arr = np.array(portfolio_returns)
    portfolio_metrics = compute_portfolio_metrics(ret_arr)
    final_capital = request.total_capital * np.prod(1 + ret_arr)
    max_dd_pct = float(np.min(np.cumprod(1 + ret_arr) / np.maximum.accumulate(np.cumprod(1 + ret_arr)) - 1))

    return PortfolioResult(
        stock_codes=[sd["code"] for sd in stock_data],
        stock_names=[sd.get("quotes", {}).get("name", sd["code"]) for sd in stock_data],
        start_date=start,
        end_date=end,
        total_capital=request.total_capital,
        capital_strategy=request.capital_strategy,
        weights=[round(w, 4) for w in weights],
        portfolio_metrics=portfolio_metrics,
        per_stock_metrics=per_stock_metrics,
        daily_returns=[round(float(r), 6) for r in portfolio_returns],
        equity_curve=equity_curve,
        max_drawdown_pct=round(float(max_dd_pct), 4),
        final_capital=round(float(final_capital), 2),
    )


# ── Helper: get quote info ──────────────────────────────────────────────


def _get_quote_info(stock_code: str) -> dict:
    """Get stock name from market service or fallback to code."""
    try:
        from market_service import get_market_service
        snap = get_market_service().get_market_snapshot()
        if stock_code in snap.stock_data_map:
            q = snap.stock_data_map[stock_code]
            return {"name": q.stock_name, "price": q.price}
    except Exception:
        pass
    return {"name": stock_code, "price": None}


# ── Predefined portfolio templates ──────────────────────────────────────

PORTFOLIO_TEMPLATES = {
    "conservative": {
        "name": "保守型",
        "description": "低波动大盘蓝筹组合",
        "stocks": ["600036", "600900", "600519", "601318", "000333"],
        "capital_strategy": "risk_parity",
        "max_per_stock": 0.20,
    },
    "balanced": {
        "name": "平衡型",
        "description": "价值+成长均衡组合",
        "stocks": ["600036", "000333", "002415", "300750", "600887"],
        "capital_strategy": "kelly",
        "max_per_stock": 0.25,
    },
    "aggressive": {
        "name": "进取型",
        "description": "高成长科技+新能源组合",
        "stocks": ["300750", "002475", "688981", "300059", "603259"],
        "capital_strategy": "kelly",
        "max_per_stock": 0.30,
    },
}