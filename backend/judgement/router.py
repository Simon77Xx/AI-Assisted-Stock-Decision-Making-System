"""FastAPI routes for AI judgement.

The AI judgement endpoint now accepts a minimal request (stock_code + backtest_version)
and loads indicator data from the server-side BacktestSnapshot stored in state.
This eliminates client-side indicator recomputation and ensures data consistency.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from judgement.service import AISummaryResponse, IndicatorInput, get_ai_judgement
from judgement.state import get_snapshot_by_version

router = APIRouter(prefix="/api/ai-judgement", tags=["AI Judgement"])


class AIJudgementRequest(BaseModel):
    """Minimal request — indicators are loaded from server-side snapshot by version."""

    stock_code: str = Field(..., description="Stock code")
    backtest_version: str = Field(..., description="Backtest version ID")
    stock_name: str = Field(default="", description="Stock name (optional)")


def _snapshot_to_indicator_input(snapshot, request: AIJudgementRequest) -> IndicatorInput:
    """Convert a BacktestSnapshot to an IndicatorInput for the AI service."""
    return IndicatorInput(
        stock_code=request.stock_code,
        stock_name=request.stock_name,
        current_price=snapshot.current_price,
        ma5=snapshot.ma5,
        ma20=snapshot.ma20,
        ma60=snapshot.ma60,
        ma_cross_status=snapshot.ma_cross_status,
        cross_date=snapshot.cross_date,
        trend_filter_status=snapshot.trend_filter_status,
        return_5d=snapshot.return_5d,
        return_20d=snapshot.return_20d,
        volume_ratio=snapshot.volume_ratio,
        current_position=snapshot.current_position,
        current_signal=snapshot.current_signal,
        max_drawdown=snapshot.max_drawdown,
        backtest_version=snapshot.version_id,
        backtest_timestamp=snapshot.created_at,
        data_warnings=snapshot.data_warnings,
        # Position state machine data for AI context
        position_state=snapshot.position_state,
        holding_days=snapshot.holding_days,
        insufficient_data=snapshot.insufficient_data,
        missing_indicators=snapshot.missing_indicators,
    )


@router.post("", response_model=AISummaryResponse)
def ai_judgement(request: AIJudgementRequest):
    snapshot = get_snapshot_by_version(request.backtest_version)
    if snapshot is None:
        raise HTTPException(status_code=409, detail="Backtest result expired or not found.")

    try:
        # Only use data from the server-side snapshot — no client-supplied indicators
        indicators = _snapshot_to_indicator_input(snapshot, request)
        return get_ai_judgement(indicators)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/health")
def health():
    return {"status": "ok"}