"""Strategy vs AI Consistency Check module.

Compares the mechanical dual-MA strategy signal with the AI recommendation
and produces a consistency verdict with plain-language explanations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ai_decision_service import AIRecommendation


@dataclass(frozen=True)
class ConsistencyResult:
    """Result of comparing strategy signal vs AI recommendation."""

    strategy_signal: str  # raw signal: "买入" / "卖出" / "持有"
    ai_decision: str  # "推荐" / "观望" / "不推荐"
    is_consistent: bool
    explanation: str  # plain-language explanation

    # For detailed display
    strategy_detail: str = ""
    ai_detail: str = ""


# ── Mapping table ──────────────────────────────────────────────────────

# How to map strategy signals to the same 3-class scale as AI
_STRATEGY_TO_THREE_CLASS: dict[str, str] = {
    "买入": "推荐",
    "卖出": "不推荐",
    "持有": "观望",
}

_CONSISTENT_EXPLANATIONS: dict[str, str] = {
    "买入": "技术指标发出买入信号，AI分析也认可当前具备投资价值，策略与AI判断一致。",
    "卖出": "技术指标发出卖出信号，AI分析也认为风险较高，策略与AI判断一致。",
    "持有": "技术指标持仓观望，AI分析也建议谨慎等待，策略与AI判断一致。",
}

_INCONSISTENT_EXPLANATIONS: dict[str, str] = {
    "买入": "技术指标发出买入信号，但AI综合市场状态和评分认为需要观望。可能原因是短期指标向好但市场整体偏弱。",
    "卖出": "技术指标发出卖出信号，但AI评分显示该股仍有一定投资价值。可能原因是个股基本面支撑较强。",
    "持有": "技术指标持有观望，但AI分析认为当前值得关注。建议结合更多信息综合判断。",
}


def _invert_decision(d: str) -> str:
    """Return the most opposite AI decision for explanation purposes."""
    mapping = {"推荐": "观望", "观望": "推荐", "不推荐": "观望"}
    return mapping.get(d, "观望")


# ── Public API ─────────────────────────────────────────────────────────


def check_consistency(
    strategy_signal: str,
    ai_recommendation: AIRecommendation,
) -> ConsistencyResult:
    """Compare the mechanical strategy signal with the AI recommendation.

    Args:
        strategy_signal: One of "买入", "卖出", "持有"
        ai_recommendation: The AI recommendation result

    Returns:
        ConsistencyResult with consistency flag and explanation.
    """
    strategy_class = _STRATEGY_TO_THREE_CLASS.get(strategy_signal, "观望")
    is_consistent = strategy_class == ai_recommendation.decision

    if is_consistent:
        explanation = _CONSISTENT_EXPLANATIONS.get(
            strategy_signal,
            "技术指标与AI分析判断方向一致，市场信号较为明确。",
        )
    else:
        explanation = _INCONSISTENT_EXPLANATIONS.get(
            strategy_signal,
            f"技术指标建议「{strategy_signal}」，但AI分析建议「{ai_recommendation.decision}」。{ai_recommendation.reasoning}",
        )

    return ConsistencyResult(
        strategy_signal=strategy_signal,
        ai_decision=ai_recommendation.decision,
        is_consistent=is_consistent,
        explanation=explanation,
        strategy_detail=_strategy_detail(strategy_signal),
        ai_detail=_ai_detail(ai_recommendation),
    )


def _strategy_detail(signal: str) -> str:
    """Plain-language explanation of what the strategy signal means."""
    details = {
        "买入": "双均线策略发出买入信号：短期均线上穿长期均线（金叉），且价格处于60日均线上方（趋势向上）。",
        "卖出": "双均线策略发出卖出信号：短期均线下穿长期均线（死叉），或价格跌破60日均线（趋势转弱）。",
        "持有": "双均线策略维持当前持仓状态，无新的买卖信号。",
    }
    return details.get(signal, "暂无策略信号。")


def _ai_detail(rec: AIRecommendation) -> str:
    """Plain-language explanation of the AI recommendation."""
    risk_cn = {"Low": "低", "Medium": "中", "High": "高"}.get(rec.risk_level, "中")
    return (
        f"AI分析建议「{rec.decision}」，风险等级「{risk_cn}」，"
        f"信心指数「{rec.confidence:.0%}」。{rec.reasoning}"
    )