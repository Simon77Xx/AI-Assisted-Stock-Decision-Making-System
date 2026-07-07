"""Beginner-friendly output formatting module.

Translates technical analysis results into plain Chinese that
non-professional users can easily understand.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ai_decision_service import AIRecommendation
from market_service import MarketSnapshot, StockRealtimeQuote
from scoring_engine import StockRanking, StockScoreResult
from strategy_ai_compare import ConsistencyResult


# ---------------------------------------------------------------------------
# Beginner-friendly data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BeginnerStockInfo:
    """A stock explained in plain language."""

    stock_code: str
    stock_name: str
    score: float  # 0-100
    suggestion: str  # "适合关注" | "暂不建议" | "高风险观望"
    reason: str  # plain-language reason
    risk_tip: str  # plain-language risk warning
    price: Optional[float] = None
    change_pct: Optional[float] = None


@dataclass(frozen=True)
class BeginnerMarketOverview:
    """Market state explained simply."""

    market_mood: str  # e.g. "市场整体偏强", "市场偏弱", "震荡格局"
    rising_count: int
    total_count: int
    recommended_stocks: list[BeginnerStockInfo]
    timestamp: str


@dataclass(frozen=True)
class BeginnerDecision:
    """Final decision output for a single stock, beginner-friendly."""

    stock_info: BeginnerStockInfo
    ai_thinking: str  # "AI认为…" in plain language
    strategy_vs_ai: str  # consistency explanation
    risk_warning: str  # risk warning
    alternatives: list[BeginnerStockInfo]  # top alternatives


@dataclass(frozen=True)
class BeginnerOutput:
    """Complete system output in beginner-friendly format."""

    market_overview: BeginnerMarketOverview
    selected_analysis: Optional[BeginnerDecision]
    timestamp: str
    data_freshness: str  # "数据时间：XXX" warning


# ---------------------------------------------------------------------------
# Mapping / translation helpers
# ---------------------------------------------------------------------------


def _score_to_suggestion(score: float) -> str:
    """Map score 0-100 to a beginner-friendly suggestion."""
    if score >= 70:
        return "适合关注"
    if score >= 45:
        return "观望为主"
    return "暂不建议"


def _score_to_risk_tip(score: float, risk_level: str) -> str:
    """Generate a plain-language risk tip."""
    tips: list[str] = []

    if risk_level == "High" or score < 30:
        tips.append("波动较大")
        tips.append("不适合重仓")
    elif risk_level == "Medium" or score < 55:
        tips.append("短期不确定性较高")
    else:
        tips.append("风险相对可控")

    if score < 20:
        tips.append("建议等待更明确的信号")
    elif score < 40:
        tips.append("需密切关注市场变化")

    return "；".join(tips) if tips else "暂无特别风险提示"


def _market_state_to_mood(state: str) -> str:
    moods = {
        "bull": "市场整体偏强，上涨个股较多",
        "bear": "市场整体偏弱，下跌个股较多",
        "sideways": "市场处于震荡格局，趋势不明确",
        "unknown": "市场数据暂无法判断整体状态",
    }
    return moods.get(state, "市场状态未知")


def _change_to_str(change_pct: Optional[float]) -> str:
    if change_pct is None:
        return "未知"
    if change_pct > 0:
        return f"上涨{change_pct * 100:.1f}%"
    return f"下跌{abs(change_pct) * 100:.1f}%"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_market_overview(
    ranking: StockRanking,
    market_snapshot: MarketSnapshot,
) -> BeginnerMarketOverview:
    """Build a beginner-friendly market overview from ranking data."""
    mood = _market_state_to_mood(market_snapshot.market_state)

    total = len(market_snapshot.stock_data_map)
    rising = sum(
        1 for q in market_snapshot.stock_data_map.values()
        if q.change_pct > 0
    )

    recommended: list[BeginnerStockInfo] = []
    for r in ranking.rankings:
        quote = market_snapshot.stock_data_map.get(r.stock_code)
        suggestion = _score_to_suggestion(r.score)
        risk = _score_to_risk_tip(r.score, "Medium")
        recommended.append(BeginnerStockInfo(
            stock_code=r.stock_code,
            stock_name=r.stock_name,
            score=r.score,
            suggestion=suggestion,
            reason=r.reason,
            risk_tip=risk,
            price=quote.price if quote else None,
            change_pct=quote.change_pct if quote else None,
        ))

    return BeginnerMarketOverview(
        market_mood=mood,
        rising_count=rising,
        total_count=total,
        recommended_stocks=recommended,
        timestamp=market_snapshot.timestamp,
    )


def build_stock_decision(
    stock_result: StockScoreResult,
    ai_rec: AIRecommendation,
    consistency: ConsistencyResult,
    market_snapshot: MarketSnapshot,
    alternatives_rankings: list[StockScoreResult],
) -> BeginnerDecision:
    """Build a beginner-friendly decision for a single stock."""
    quote = market_snapshot.stock_data_map.get(stock_result.stock_code)

    # AI thinking in plain language
    risk_cn = {"Low": "较低", "Medium": "中等", "High": "较高"}.get(ai_rec.risk_level, "中等")
    ai_thinking = (
        f"AI认为当前「{ai_rec.decision}」，风险等级「{risk_cn}」，"
        f"信心指数{ai_rec.confidence:.0%}。{ai_rec.reasoning}"
    )

    # Use AI risk level for the final risk tip
    risk_tip = _score_to_risk_tip(stock_result.score, ai_rec.risk_level)

    stock_info = BeginnerStockInfo(
        stock_code=stock_result.stock_code,
        stock_name=stock_result.stock_name,
        score=stock_result.score,
        suggestion=_score_to_suggestion(stock_result.score),
        reason=stock_result.reason,
        risk_tip=risk_tip,
        price=quote.price if quote else None,
        change_pct=quote.change_pct if quote else None,
    )

    alt_stocks: list[BeginnerStockInfo] = []
    for alt in alternatives_rankings[:3]:
        if alt.stock_code == stock_result.stock_code:
            continue
        alt_quote = market_snapshot.stock_data_map.get(alt.stock_code)
        alt_stocks.append(BeginnerStockInfo(
            stock_code=alt.stock_code,
            stock_name=alt.stock_name,
            score=alt.score,
            suggestion=_score_to_suggestion(alt.score),
            reason=alt.reason,
            risk_tip=_score_to_risk_tip(alt.score, "Medium"),
            price=alt_quote.price if alt_quote else None,
            change_pct=alt_quote.change_pct if alt_quote else None,
        ))

    return BeginnerDecision(
        stock_info=stock_info,
        ai_thinking=ai_thinking,
        strategy_vs_ai=consistency.explanation,
        risk_warning=(
            f"风险提示：{risk_tip}。{ai_rec.reasoning} "
            "以上分析仅供参考，不构成投资建议，市场存在不确定性，请结合自身情况谨慎决策。"
        ),
        alternatives=alt_stocks,
    )


def build_full_output(
    market_overview: BeginnerMarketOverview,
    selected_decision: Optional[BeginnerDecision],
    timestamp: str,
    snapshot_id: str,
) -> BeginnerOutput:
    """Build the complete beginner-friendly output."""
    data_freshness = f"数据时间：{timestamp}（快照ID：{snapshot_id}）"
    return BeginnerOutput(
        market_overview=market_overview,
        selected_analysis=selected_decision,
        timestamp=timestamp,
        data_freshness=data_freshness,
    )