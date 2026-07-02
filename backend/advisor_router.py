"""FastAPI router for AI-assisted stock selection endpoints.

All new endpoints are incremental additions — no existing backtest routes are modified.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ai_stock_advisor import get_advisor

router = APIRouter(prefix="/api/advisor", tags=["AI Stock Advisor"])


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
    except Exception as e:
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


@router.get("/health")
def health():
    return {"status": "ok", "service": "AI Stock Advisor"}