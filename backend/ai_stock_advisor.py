"""AI Stock Advisor — main orchestration service.

Ties together:
1. Market Data Service (real-time snapshots)
2. Scoring Engine (multi-stock ranking)
3. AI Decision Service (AI recommendations)
4. Strategy-AI Comparison (consistency checks)
5. Beginner Output (plain-language formatting)

This is the primary entry point for the "AI辅助选股系统".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd

from ai_decision_service import AIRecommendation, get_ai_recommendation
from beginner_output import (
    BeginnerDecision,
    BeginnerMarketOverview,
    BeginnerOutput,
    BeginnerStockInfo,
    build_full_output,
    build_market_overview,
    build_stock_decision,
    _score_to_risk_tip,
    _score_to_suggestion,
)
from market_service import MarketSnapshot, get_market_service
from scoring_engine import (
    StockRanking,
    StockScoreResult,
    get_cached_ranking,
    rank_stocks,
    score_single_stock,
    update_ai_confidence,
)
from strategy_ai_compare import check_consistency

# ---------------------------------------------------------------------------
# Final output data type (matches the spec's final_output JSON structure)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FinalAdvisorOutput:
    """The complete system output (machine-readable)."""

    market_state: dict[str, Any]
    top_stocks: list[dict[str, Any]]
    selected_stock_analysis: Optional[dict[str, Any]] = None
    ai_recommendation: Optional[dict[str, Any]] = None
    risk_warning: Optional[dict[str, Any]] = None
    beginner_output: Optional[dict[str, Any]] = None
    timestamp: str = ""


# ---------------------------------------------------------------------------
# Main advisor
# ---------------------------------------------------------------------------


class AIStockAdvisor:
    """Main orchestrator for the AI-assisted stock selection system."""

    def __init__(self, cache_ttl_seconds: int = 300):
        self._market_service = get_market_service(cache_ttl_seconds)

    # ── Market operations ──────────────────────────────────────────────

    def get_market_overview(
        self,
        stock_codes: Optional[list[str]] = None,
        force_refresh: bool = False,
    ) -> tuple[MarketSnapshot, StockRanking]:
        """Get current market snapshot and stock ranking."""
        snapshot = self._market_service.get_market_snapshot(
            stock_codes=stock_codes,
            force_refresh=force_refresh,
        )
        ranking = rank_stocks(snapshot, force_refresh=force_refresh)
        return snapshot, ranking

    def refresh_market(self) -> tuple[MarketSnapshot, StockRanking]:
        """Force refresh market data and re-rank all stocks."""
        return self.get_market_overview(force_refresh=True)

    # ── Single stock analysis ──────────────────────────────────────────

    def analyze_stock(
        self,
        stock_code: str,
        stock_name: str,
        market_snapshot: MarketSnapshot,
        ranking: StockRanking,
    ) -> dict[str, Any]:
        """Full analysis of a single stock: score + AI + consistency.

        Returns a dictionary ready for JSON serialization.
        """
        # 1. Get the stock quote from snapshot
        quote = market_snapshot.stock_data_map.get(stock_code)
        if quote is None:
            return {"error": f"股票 {stock_code} 不在当前市场快照中"}

        # 2. Score the stock (or use cached ranking)
        scored = None
        for r in ranking.rankings:
            if r.stock_code == stock_code:
                scored = r
                break
        if scored is None:
            scored = score_single_stock(
                stock_code=stock_code,
                stock_name=stock_name or quote.stock_name,
                quote=quote,
                snapshot_id=market_snapshot.snapshot_id,
            )

        if scored is None:
            return {"error": f"无法获取 {stock_code} 的分析数据"}

        # 3. Get AI recommendation
        ai_rec = get_ai_recommendation(
            stock_code=stock_code,
            stock_name=stock_name or quote.stock_name,
            score=scored.score,
            score_reason=scored.reason,
            market_snapshot=market_snapshot,
            trend_strength=scored.trend_strength,
            volume_signal=scored.volume_signal,
            volatility=scored.volatility_adjusted_return,
            momentum=scored.momentum_score,
        )

        # 4. Update scoring with AI confidence
        update_ai_confidence(stock_code, ai_rec.confidence, market_snapshot.snapshot_id)

        # 5. Strategy-AI consistency
        from backtest_engine import compute_signals
        from data_fetcher import load_data

        try:
            df = load_data(
                stock_code,
                start_date=(datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
            )
            signals = compute_signals(df)
            if signals.empty:
                strategy_signal = "持有"
            else:
                pos = signals.iloc[-1].get("position", 0)
                if pos > 0:
                    strategy_signal = "买入"
                else:
                    recent = signals[signals["position"].diff().fillna(0) != 0]
                    if not recent.empty:
                        last_signal = recent.iloc[-1]["position"]
                        if last_signal > 0:
                            strategy_signal = "买入"
                        elif last_signal < 0:
                            strategy_signal = "卖出"
                        else:
                            strategy_signal = "持有"
                    else:
                        strategy_signal = "持有"
        except Exception:
            strategy_signal = "持有"

        consistency = check_consistency(strategy_signal, ai_rec)

        # 6. Build alternatives from ranking
        alternatives = [r for r in ranking.rankings if r.stock_code != stock_code][:3]

        # 7. Build beginner-friendly output
        beginner_decision = build_stock_decision(
            stock_result=scored,
            ai_rec=ai_rec,
            consistency=consistency,
            market_snapshot=market_snapshot,
            alternatives_rankings=alternatives,
        )

        return self._decision_to_dict(
            scored=scored,
            ai_rec=ai_rec,
            consistency=consistency,
            beginner_decision=beginner_decision,
            market_snapshot=market_snapshot,
            strategy_signal=strategy_signal,
        )

    # ── Full output ────────────────────────────────────────────────────

    def get_full_advisor_output(
        self,
        selected_stock: Optional[str] = None,
        stock_codes: Optional[list[str]] = None,
        force_refresh: bool = False,
    ) -> FinalAdvisorOutput:
        """Get the complete system output: market + rankings + analysis."""
        snapshot, ranking = self.get_market_overview(
            stock_codes=stock_codes,
            force_refresh=force_refresh,
        )

        # Market state
        market_state_dict = {
            "state": snapshot.market_state,
            "timestamp": snapshot.timestamp,
            "snapshot_id": snapshot.snapshot_id,
            "stock_count": len(snapshot.stock_data_map),
        }

        # Top stocks
        top_stocks = []
        for r in ranking.rankings:
            quote = snapshot.stock_data_map.get(r.stock_code)
            top_stocks.append({
                "stock": r.stock_code,
                "name": r.stock_name,
                "score": r.score,
                "reason": r.reason,
                "price": quote.price if quote else None,
                "change_pct": quote.change_pct if quote else None,
            })

        # Selected stock analysis
        selected_analysis = None
        ai_recommendation = None
        risk_warning = None
        beginner = None

        if selected_stock and selected_stock in snapshot.stock_data_map:
            stock_name = snapshot.stock_data_map[selected_stock].stock_name
            analysis = self.analyze_stock(
                stock_code=selected_stock,
                stock_name=stock_name,
                market_snapshot=snapshot,
                ranking=ranking,
            )
            selected_analysis = analysis.get("selected_stock_analysis")
            ai_recommendation = analysis.get("ai_recommendation")
            risk_warning = analysis.get("risk_warning")
            beginner = analysis.get("beginner_output")

        return FinalAdvisorOutput(
            market_state=market_state_dict,
            top_stocks=top_stocks,
            selected_stock_analysis=selected_analysis,
            ai_recommendation=ai_recommendation,
            risk_warning=risk_warning,
            beginner_output=beginner,
            timestamp=snapshot.timestamp,
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _decision_to_dict(
        self,
        scored: StockScoreResult,
        ai_rec: AIRecommendation,
        consistency,
        beginner_decision: BeginnerDecision,
        market_snapshot: MarketSnapshot,
        strategy_signal: str,
    ) -> dict[str, Any]:
        """Convert analysis results to a JSON-serializable dict."""
        return {
            "selected_stock_analysis": {
                "stock_code": scored.stock_code,
                "stock_name": scored.stock_name,
                "score": scored.score,
                "sub_scores": {
                    "trend_strength": scored.trend_strength,
                    "volume_signal": scored.volume_signal,
                    "volatility_adjusted_return": scored.volatility_adjusted_return,
                    "ai_confidence": scored.ai_confidence,
                    "momentum_score": scored.momentum_score,
                },
                "technical_reason": scored.reason,
                "strategy_signal": strategy_signal,
                "snapshot_id": scored.snapshot_id,
            },
            "ai_recommendation": {
                "decision": ai_rec.decision,
                "reasoning": ai_rec.reasoning,
                "risk_level": ai_rec.risk_level,
                "confidence": ai_rec.confidence,
                "alternatives": ai_rec.alternatives,
            },
            "strategy_ai_consistency": {
                "is_consistent": consistency.is_consistent,
                "strategy_signal": consistency.strategy_signal,
                "ai_decision": consistency.ai_decision,
                "explanation": consistency.explanation,
                "strategy_detail": consistency.strategy_detail,
                "ai_detail": consistency.ai_detail,
            },
            "risk_warning": {
                "risk_level": ai_rec.risk_level,
                "data_timestamp": market_snapshot.timestamp,
                "data_snapshot_id": market_snapshot.snapshot_id,
                "disclaimer": (
                    "以上分析仅基于历史技术指标和实时市场数据的辅助参考，"
                    "不构成投资建议。市场存在不确定性，请结合自身判断谨慎决策。"
                ),
            },
            "beginner_output": {
                "stock_summary": {
                    "name": beginner_decision.stock_info.stock_name,
                    "code": beginner_decision.stock_info.stock_code,
                    "suggestion": beginner_decision.stock_info.suggestion,
                    "reason": beginner_decision.stock_info.reason,
                    "risk_tip": beginner_decision.stock_info.risk_tip,
                    "price": beginner_decision.stock_info.price,
                    "change": beginner_decision.stock_info.change_pct,
                    "score": beginner_decision.stock_info.score,
                },
                "ai_thinking": beginner_decision.ai_thinking,
                "strategy_vs_ai": beginner_decision.strategy_vs_ai,
                "risk_warning": beginner_decision.risk_warning,
                "alternatives": [
                    {
                        "code": a.stock_code,
                        "name": a.stock_name,
                        "score": a.score,
                        "suggestion": a.suggestion,
                        "reason": a.reason,
                        "risk_tip": a.risk_tip,
                    }
                    for a in beginner_decision.alternatives
                ],
            },
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_advisor: Optional[AIStockAdvisor] = None
_advisor_lock = __import__("threading").Lock()


def get_advisor(cache_ttl_seconds: int = 300) -> AIStockAdvisor:
    """Get the singleton AIStockAdvisor instance."""
    global _advisor
    if _advisor is None:
        with _advisor_lock:
            if _advisor is None:
                _advisor = AIStockAdvisor(cache_ttl_seconds=cache_ttl_seconds)
    return _advisor