"""FastAPI router for AI-assisted stock selection endpoints.

All new endpoints are incremental additions — no existing backtest routes are modified.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ai_stock_advisor import get_advisor
from data_fetcher import load_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/advisor", tags=["AI Stock Advisor"])

# Pre-defined watchlist for quick comparison
WATCHLIST_OPTIONS = [
    {"code": "000001", "name": "平安银行"},
    {"code": "000002", "name": "万科A"},
    {"code": "000333", "name": "美的集团"},
    {"code": "000651", "name": "格力电器"},
    {"code": "000858", "name": "五粮液"},
    {"code": "002415", "name": "海康威视"},
    {"code": "002475", "name": "立讯精密"},
    {"code": "300059", "name": "东方财富"},
    {"code": "300750", "name": "宁德时代"},
    {"code": "600036", "name": "招商银行"},
    {"code": "600276", "name": "恒瑞医药"},
    {"code": "600519", "name": "贵州茅台"},
    {"code": "600887", "name": "伊利股份"},
    {"code": "600900", "name": "长江电力"},
    {"code": "601318", "name": "中国平安"},
    {"code": "601857", "name": "中国石油"},
    {"code": "603259", "name": "药明康德"},
    {"code": "688981", "name": "中芯国际"},
]


@router.get("/stock-list")
def api_stock_list():
    """Return the full watchlist of available stocks for selection."""
    return {"stocks": WATCHLIST_OPTIONS}


@router.get("/market-overview")
def api_market_overview(
    force_refresh: bool = Query(False, description="Force refresh market data"),
):
    """Get current market overview with stock rankings (beginner-friendly)."""
    try:
        advisor = get_advisor()
        snapshot, ranking = advisor.get_market_overview(
            force_refresh=force_refresh,
        )

        if not snapshot.stock_data_map:
            raise HTTPException(
                status_code=503,
                detail="市场数据获取失败：akshare 无法连接到国内金融数据源。请检查代理配置（HTTP_PROXY/HTTPS_PROXY）或网络连接。",
            )

        beginner_overview = __import__(
            "beginner_output", fromlist=["build_market_overview"]
        ).build_market_overview(ranking, snapshot)

        return {
            "market_state": {
                "state": snapshot.market_state,
                "timestamp": snapshot.timestamp,
                "snapshot_id": snapshot.snapshot_id,
                "stock_count": len(snapshot.stock_data_map),
            },
            "top_stocks": [
                {
                    "stock": r.stock_code,
                    "name": r.stock_name,
                    "score": r.score,
                    "reason": r.reason,
                    "price": (
                        snapshot.stock_data_map[r.stock_code].price
                        if r.stock_code in snapshot.stock_data_map
                        else None
                    ),
                    "change_pct": (
                        snapshot.stock_data_map[r.stock_code].change_pct
                        if r.stock_code in snapshot.stock_data_map
                        else None
                    ),
                }
                for r in ranking.rankings
            ],
            "beginner_market_overview": {
                "market_mood": beginner_overview.market_mood,
                "rising_count": beginner_overview.rising_count,
                "total_count": beginner_overview.total_count,
                "timestamp": beginner_overview.timestamp,
                "recommended_stocks": [
                    {
                        "stock_code": s.stock_code,
                        "stock_name": s.stock_name,
                        "score": s.score,
                        "suggestion": s.suggestion,
                        "reason": s.reason,
                        "risk_tip": s.risk_tip,
                        "price": s.price,
                        "change_pct": s.change_pct,
                    }
                    for s in beginner_overview.recommended_stocks
                ],
            },
            "timestamp": snapshot.timestamp,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Market overview failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-stock")
def api_analyze_stock(
    stock_code: str = Query(..., description="Stock code to analyze"),
    stock_name: str = Query("", description="Optional stock name"),
    force_refresh: bool = Query(False, description="Force refresh market data"),
):
    """Full analysis of a single stock: score + AI + consistency + beginner output."""
    try:
        advisor = get_advisor()
        snapshot, ranking = advisor.get_market_overview(
            force_refresh=force_refresh,
        )

        if stock_code not in snapshot.stock_data_map:
            raise HTTPException(
                status_code=404,
                detail=f"股票 {stock_code} 不在当前市场数据中。请检查股票代码是否正确。",
            )

        result = advisor.analyze_stock(
            stock_code=stock_code,
            stock_name=stock_name or snapshot.stock_data_map[stock_code].stock_name,
            market_snapshot=snapshot,
            ranking=ranking,
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/full-output")
def api_full_output(
    selected_stock: Optional[str] = Query(None, description="Stock code for deep analysis"),
    force_refresh: bool = Query(False, description="Force refresh market data"),
):
    """Get the complete system output: market state + rankings + selected stock analysis."""
    try:
        advisor = get_advisor()
        output = advisor.get_full_advisor_output(
            selected_stock=selected_stock,
            force_refresh=force_refresh,
        )

        return {
            "market_state": output.market_state,
            "top_stocks": output.top_stocks,
            "selected_stock_analysis": output.selected_stock_analysis,
            "ai_recommendation": output.ai_recommendation,
            "risk_warning": output.risk_warning,
            "beginner_output": output.beginner_output,
            "timestamp": output.timestamp,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
def api_refresh_market():
    """Force refresh all market data and re-rank stocks."""
    try:
        advisor = get_advisor()
        snapshot, ranking = advisor.refresh_market()
        return {
            "status": "ok",
            "snapshot_id": snapshot.snapshot_id,
            "timestamp": snapshot.timestamp,
            "market_state": snapshot.market_state,
            "stocks_analyzed": len(ranking.rankings),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare-stocks")
def api_compare_stocks(
    stock_codes: str = Query(..., description="Comma-separated stock codes, e.g. 000001,600519,000333"),
    force_refresh: bool = Query(False, description="Force refresh market data"),
):
    """Compare multiple stocks side by side: score, price, change, AI decision."""
    try:
        advisor = get_advisor()
        snapshot, ranking = advisor.get_market_overview(
            force_refresh=force_refresh,
        )

        codes = [c.strip() for c in stock_codes.split(",") if c.strip()]
        if len(codes) < 2:
            raise HTTPException(status_code=400, detail="至少选择两只股票进行对比")
        if len(codes) > 6:
            raise HTTPException(status_code=400, detail="最多对比6只股票")

        results = []
        for code in codes:
            if code not in snapshot.stock_data_map:
                continue
            name = snapshot.stock_data_map[code].stock_name
            result = advisor.analyze_stock(
                stock_code=code,
                stock_name=name,
                market_snapshot=snapshot,
                ranking=ranking,
            )
            if "error" not in result:
                results.append(result)

        return {
            "stocks": results,
            "timestamp": snapshot.timestamp,
            "snapshot_id": snapshot.snapshot_id,
            "total_compared": len(results),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Stock comparison failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock-chart")
def api_stock_chart(
    stock_code: str = Query(..., description="Stock code"),
    days: int = Query(365, description="Number of trading days of history"),
):
    """Get historical price chart data with MA lines for a stock.

    Returns OHLC + MA5/MA20/MA60 for the specified lookback period.
    """
    try:
        from datetime import datetime, timedelta, timezone

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days + 100)  # buffer for non-trading days
        df = load_data(
            stock_code,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
        )
        if df.empty:
            raise HTTPException(status_code=404, detail=f"股票 {stock_code} 无历史数据")

        # Compute MAs
        df = df.sort_values("date").tail(days).reset_index(drop=True)
        df["MA5"] = df["close"].rolling(window=5, min_periods=1).mean()
        df["MA20"] = df["close"].rolling(window=20, min_periods=1).mean()
        df["MA60"] = df["close"].rolling(window=60, min_periods=1).mean()

        chart_data = []
        for _, row in df.iterrows():
            chart_data.append({
                "date": row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]),
                "open": round(float(row["open"]), 2),
                "close": round(float(row["close"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "volume": float(row["volume"]),
                "MA5": round(float(row["MA5"]), 2) if pd.notna(row["MA5"]) else None,
                "MA20": round(float(row["MA20"]), 2) if pd.notna(row["MA20"]) else None,
                "MA60": round(float(row["MA60"]), 2) if pd.notna(row["MA60"]) else None,
            })

        stock_name = ""
        try:
            from market_service import get_market_service
            snap = get_market_service().get_market_snapshot()
            if stock_code in snap.stock_data_map:
                stock_name = snap.stock_data_map[stock_code].stock_name
        except Exception:
            pass

        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "chart_data": chart_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Stock chart data failed")
        raise HTTPException(status_code=500, detail=str(e))


def health():
    return {"status": "ok", "service": "AI Stock Advisor"}


# ═══════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: Financial Data
# ═══════════════════════════════════════════════════════════════════════


@router.get("/financial-data")
def api_financial_data(
    stock_code: str = Query(..., description="Stock code"),
    force_refresh: bool = Query(False, description="Force refresh financial data"),
):
    """Get financial metrics for a stock (PE/PB/ROE/growth/etc.)."""
    try:
        from financial_analyzer import get_financial_metrics, invalidate_cache

        if force_refresh:
            invalidate_cache(stock_code)

        fin = get_financial_metrics(stock_code)
        if not fin or not fin.has_data:
            return {
                "stock_code": stock_code,
                "financial_metrics": None,
                "note": "暂无财务数据",
            }

        return {
            "stock_code": stock_code,
            "financial_metrics": {
                "pe_ttm": fin.pe_ttm,
                "roe": fin.roe,
                "net_profit_margin": fin.net_profit_margin,
                "gross_margin": fin.gross_margin,
                "revenue_growth": fin.revenue_growth,
                "net_profit_growth": fin.net_profit_growth,
                "debt_ratio": fin.debt_ratio,
                "current_ratio": fin.current_ratio,
                "eps": fin.eps,
                "bvps": fin.bvps,
                "report_date": fin.report_date,
            },
        }
    except Exception as e:
        logger.exception("Financial data fetch failed")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: Trading Executor
# ═══════════════════════════════════════════════════════════════════════


@router.get("/trading/account")
def api_trading_account(
    mode: str = Query("simulated", description="'simulated' or 'ths'"),
):
    """Get trading account info (balance, positions, P&L)."""
    try:
        from trading_executor import get_trading_executor

        executor = get_trading_executor(mode=mode)
        account = executor.get_account_info()

        return {
            "account_id": account.account_id,
            "name": executor.name,
            "connected": executor.is_connected,
            "total_asset": account.total_asset,
            "available_cash": account.available_cash,
            "frozen_cash": account.frozen_cash,
            "market_value": account.market_value,
            "daily_profit": account.daily_profit,
            "positions": [
                {
                    "stock_code": p.stock_code,
                    "stock_name": p.stock_name,
                    "quantity": p.quantity,
                    "available_quantity": p.available_quantity,
                    "cost_price": p.cost_price,
                    "current_price": p.current_price,
                    "market_value": p.market_value,
                    "profit_pct": p.profit_pct,
                }
                for p in account.positions
            ],
            "update_time": account.update_time,
        }
    except Exception as e:
        logger.exception("Account info failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading/order")
def api_place_order(
    stock_code: str = Query(..., description="Stock code"),
    stock_name: str = Query("", description="Stock name"),
    side: str = Query("buy", description="'buy' or 'sell'"),
    order_type: str = Query("market", description="'market' or 'limit'"),
    quantity: int = Query(100, description="Number of shares"),
    price: Optional[float] = Query(None, description="Limit price"),
    mode: str = Query("simulated", description="'simulated' or 'ths'"),
):
    """Place a trade order (simulated or real via 同花顺)."""
    try:
        from trading_executor import (
            OrderSide,
            OrderType,
            get_trading_executor,
        )

        executor = get_trading_executor(mode=mode)

        side_enum = OrderSide.BUY if side == "buy" else OrderSide.SELL
        type_enum = OrderType.LIMIT if order_type == "limit" else OrderType.MARKET

        order = executor.place_order(
            stock_code=stock_code,
            stock_name=stock_name,
            side=side_enum,
            order_type=type_enum,
            quantity=quantity,
            price=price,
        )

        return {
            "order_id": order.order_id,
            "stock_code": order.stock_code,
            "stock_name": order.stock_name,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "price": order.price,
            "quantity": order.quantity,
            "filled_quantity": order.filled_quantity,
            "status": order.status.value,
            "note": order.note or "",
            "reject_reason": order.reject_reason or "",
            "created_at": order.created_at,
        }
    except Exception as e:
        logger.exception("Order placement failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading/positions")
def api_trading_positions(
    mode: str = Query("simulated", description="'simulated' or 'ths'"),
):
    """Get current trading positions."""
    try:
        from trading_executor import get_trading_executor

        executor = get_trading_executor(mode=mode)
        positions = executor.get_positions()

        return {
            "positions": [
                {
                    "stock_code": p.stock_code,
                    "stock_name": p.stock_name,
                    "quantity": p.quantity,
                    "available_quantity": p.available_quantity,
                    "cost_price": p.cost_price,
                    "current_price": p.current_price,
                    "market_value": p.market_value,
                    "profit_pct": p.profit_pct,
                    "profit_amount": p.profit_amount,
                }
                for p in positions
            ],
            "total_count": len(positions),
        }
    except Exception as e:
        logger.exception("Positions fetch failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading/orders")
def api_order_history(
    mode: str = Query("simulated", description="'simulated' or 'ths'"),
    limit: int = Query(50, description="Max orders to return"),
):
    """Get recent order history."""
    try:
        from trading_executor import get_trading_executor

        executor = get_trading_executor(mode=mode)
        orders = executor.get_order_history(limit=limit)

        return {
            "orders": [
                {
                    "order_id": o.order_id,
                    "stock_code": o.stock_code,
                    "stock_name": o.stock_name,
                    "side": o.side.value,
                    "order_type": o.order_type.value,
                    "price": o.price,
                    "quantity": o.quantity,
                    "filled_quantity": o.filled_quantity,
                    "status": o.status.value,
                    "note": o.note or "",
                    "reject_reason": o.reject_reason or "",
                    "created_at": o.created_at,
                    "updated_at": o.updated_at,
                }
                for o in orders
            ],
            "total_count": len(orders),
        }
    except Exception as e:
        logger.exception("Order history failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading/reset")
def api_reset_trading(
    mode: str = Query("simulated", description="Only for 'simulated' mode"),
    initial_cash: float = Query(100_000.0, description="Reset cash amount"),
):
    """Reset simulated trading account to initial state."""
    try:
        from trading_executor import SimulatedTradingExecutor, reset_executor

        reset_executor()
        return {
            "status": "ok",
            "message": f"模拟交易账户已重置，初始资金 {initial_cash:.0f} 元",
            "mode": mode,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ═══════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: Technical Indicators
# ═══════════════════════════════════════════════════════════════════════


@router.get("/technical-indicators")
def api_technical_indicators(
    stock_code: str = Query(..., description="Stock code"),
    days: int = Query(365, description="Lookback period in days"),
):
    """Get MACD, RSI, Bollinger Bands, KDJ, ATR signals for a stock."""
    try:
        from datetime import datetime, timedelta, timezone
        from technical_indicators import compute_indicator_signals, composite_technical_score

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days + 100)
        df = load_data(
            stock_code,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
        )
        if df.empty:
            raise HTTPException(status_code=404, detail=f"股票 {stock_code} 无数据")

        signals = compute_indicator_signals(df)
        composite = composite_technical_score(signals)

        stock_name = ""
        try:
            from market_service import get_market_service
            snap = get_market_service().get_market_snapshot()
            if stock_code in snap.stock_data_map:
                stock_name = snap.stock_data_map[stock_code].stock_name
        except Exception:
            pass

        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "composite_score": round(composite, 3),
            "indicators": signals,
            "timestamp": end.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Technical indicators failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-timeframe")
def api_multi_timeframe(
    stock_code: str = Query(..., description="Stock code"),
    days: int = Query(730, description="Lookback days for weekly/monthly"),
):
    """Analyze a stock across daily, weekly, and monthly timeframes."""
    try:
        from datetime import datetime, timedelta, timezone
        from technical_indicators import analyze_timeframe, composite_technical_score

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days + 100)
        df = load_data(
            stock_code,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
        )
        if df.empty:
            raise HTTPException(status_code=404, detail=f"股票 {stock_code} 无数据")

        timeframes = {}
        for name in ["daily", "weekly", "monthly"]:
            signals = analyze_timeframe(df, timeframe=name)
            composite = composite_technical_score(signals) if signals else 0.5
            timeframes[name] = {
                "composite_score": round(composite, 3),
                "data_points": len(df) // (1 if name == "daily" else (5 if name == "weekly" else 21)),
                "indicators": signals,
            }

        scores = [tf["composite_score"] for tf in timeframes.values()]
        consensus = "bullish" if all(s >= 0.55 for s in scores) else (
            "bearish" if all(s <= 0.45 for s in scores) else "mixed"
        )

        stock_name = ""
        try:
            from market_service import get_market_service
            snap = get_market_service().get_market_snapshot()
            if stock_code in snap.stock_data_map:
                stock_name = snap.stock_data_map[stock_code].stock_name
        except Exception:
            pass

        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "consensus": consensus,
            "timeframes": timeframes,
            "timestamp": end.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Multi-timeframe analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: Portfolio Backtest
# ═══════════════════════════════════════════════════════════════════════


@router.get("/portfolio-templates")
def api_portfolio_templates():
    """Get predefined portfolio templates for quick backtesting."""
    try:
        from portfolio_backtest import PORTFOLIO_TEMPLATES
        return {"templates": PORTFOLIO_TEMPLATES}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio-backtest")
def api_portfolio_backtest(
    stock_codes: str = Query(..., description="Comma-separated stock codes"),
    capital_strategy: str = Query("equal", description="'equal' | 'kelly' | 'risk_parity'"),
    total_capital: float = Query(100_000.0, description="Initial capital"),
    max_per_stock: float = Query(0.25, description="Max allocation per stock"),
    start_date: str = Query("", description="Start date YYYY-MM-DD"),
    end_date: str = Query("", description="End date YYYY-MM-DD"),
):
    """Run a portfolio-level backtest across multiple stocks."""
    try:
        from portfolio_backtest import PortfolioBacktestRequest, run_portfolio_backtest

        codes = [c.strip() for c in stock_codes.split(",") if c.strip()]
        if len(codes) < 2:
            raise HTTPException(status_code=400, detail="至少选择两只股票进行组合回测")
        if len(codes) > 10:
            raise HTTPException(status_code=400, detail="最多支持10只股票的组合回测")

        request = PortfolioBacktestRequest(
            stock_codes=codes,
            start_date=start_date,
            end_date=end_date,
            total_capital=total_capital,
            capital_strategy=capital_strategy,
            max_per_stock=max_per_stock,
        )

        result = run_portfolio_backtest(request)
        if result is None:
            raise HTTPException(status_code=400, detail="组合回测失败，请检查股票代码和数据")

        return {
            "stock_codes": result.stock_codes,
            "stock_names": result.stock_names,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "total_capital": result.total_capital,
            "capital_strategy": result.capital_strategy,
            "weights": result.weights,
            "portfolio_metrics": result.portfolio_metrics,
            "per_stock_metrics": result.per_stock_metrics,
            "equity_curve": result.equity_curve,
            "max_drawdown_pct": result.max_drawdown_pct,
            "final_capital": result.final_capital,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Portfolio backtest failed")
        raise HTTPException(status_code=500, detail=str(e))
