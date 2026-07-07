"""AI Decision Service — enhanced AI selection with actionable trading guidance.

Features:
- Market state context (bull/bear/sideways)
- Stock score (0-100) from 8-factor scoring engine
- Financial data context
- Structured output: decision, reasoning, risk_level, confidence, alternatives
- **Buy/sell price range recommendation**
- **Target price and stop-loss suggestions**
- **Position sizing recommendation**
- **Disclaimer**: All outputs are for reference only
- Caching by snapshot_id + stock_code with 5-min TTL
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

from judgement.client import call_ai_model
from market_service import MarketSnapshot

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300

RISK_CN_MAP = {"Low": "较低", "Medium": "中等", "High": "较高"}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AIRecommendation:
    """Structured AI recommendation output with actionable trading guidance."""

    decision: str  # "推荐" | "观望" | "不推荐"
    reasoning: str
    risk_level: str  # "Low" | "Medium" | "High"
    confidence: float  # 0.0 – 1.0
    alternatives: list[str]  # Top 3 alternative stock codes
    snapshot_id: str
    stock_code: str

    # NEW: Actionable trading guidance
    entry_price_range: Optional[list[float]] = None  # [下限, 上限] 建议买入区间
    target_price: Optional[float] = None  # 目标价
    stop_loss_price: Optional[float] = None  # 止损位
    position_suggestion: Optional[str] = None  # e.g. "轻仓(20%)", "半仓(50%)", "重仓(80%)"
    position_ratio: Optional[float] = None  # 0.0-1.0 建议仓位比例
    financial_summary: Optional[str] = None  # 财务数据简短评价
    trading_plan: Optional[str] = None  # 操作计划（如：分批建仓、止盈策略等）

    # Disclaimer
    disclaimer: str = (
        "AI仅提供参考意见，一切交易以个人决策为准。以上分析不构成投资建议，"
        "市场存在不确定性，投资有风险，入市需谨慎。"
    )


@dataclass
class CacheEntry:
    response: AIRecommendation
    created_at: float


# ---------------------------------------------------------------------------
# Disclaimer constant
# ---------------------------------------------------------------------------

DISCLAIMER_PROMPT = """
重要声明：
- AI仅提供参考意见，一切交易以个人决策为准。
- 以上分析不构成投资建议，市场存在不确定性，投资有风险，入市需谨慎。
- 买卖点位、目标价、仓位建议均为AI基于当前数据的分析参考，实际交易请结合自身情况判断。
"""


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """你是一位专业的A股选股分析顾问。你的任务是辅助选股，提供详细的操作参考建议。

核心原则：
1. 你必须基于提供的市场状态、股票评分、技术指标和财务数据进行分析。
2. 使用概率性语言和条件性分析，避免绝对化表述。
3. 禁止使用"必涨"、"必跌"、"稳赚"、"保证"等绝对确定性词汇。
4. 输出的买卖点位和价格建议必须基于技术分析指标（支撑位/压力位），不能随意编造。
5. 输出必须是纯 JSON，不要包含额外的解释或 markdown 代码块。

JSON 输出格式：
{
  "decision": "推荐/观望/不推荐",
  "reasoning": "用一两句话说明主要理由（新手友好）",
  "risk_level": "Low/Medium/High",
  "confidence": 0.75,
  "alternatives": ["替代股票代码1", "替代股票代码2"],
  "entry_price_range": [买入下限, 买入上限],
  "target_price": 目标价,
  "stop_loss_price": 止损价,
  "position_suggestion": "仓位建议文字说明",
  "position_ratio": 0.5,
  "financial_summary": "财务数据简要评价",
  "trading_plan": "操作计划说明"
}

字段约束：
- decision: "推荐" / "观望" / "不推荐"
- reasoning: 简单易懂的中文，说明核心逻辑
- risk_level: "Low" / "Medium" / "High"
- confidence: 0.0-1.0 浮点数
- alternatives: 最多3个替代股票代码
- entry_price_range: [float, float] 或 null。建议买入价格区间
- target_price: float 或 null。目标价位
- stop_loss_price: float 或 null。止损价位
- position_suggestion: 字符串，如"轻仓(20%)"、"半仓(50%)"、"重仓(80%)"或 null
- position_ratio: 0.0-1.0 浮点数或 null
- financial_summary: 字符串，用一句话评价财务健康状况
- trading_plan: 字符串，操作策略建议（如分批建仓/止盈策略等）
"""


def _build_user_prompt(
    stock_code: str,
    stock_name: str,
    score: float,
    score_reason: str,
    market_snapshot: MarketSnapshot,
    trend_strength: float,
    volume_signal: float,
    volatility: float,
    momentum: float,
    fin_data_str: str = "",
    valuation_score: float = 0.5,
    profitability_score: float = 0.5,
    growth_score: float = 0.5,
) -> str:
    """Build the user prompt with full context for AI analysis.

    Now includes financial data and comprehensive scoring context.
    """
    market_state_cn = {
        "bull": "牛市",
        "bear": "熊市",
        "sideways": "震荡市",
        "unknown": "未知",
    }.get(market_snapshot.market_state, market_snapshot.market_state)

    quote = market_snapshot.stock_data_map.get(stock_code)
    price_str = f"{quote.price:.2f}" if quote else "未知"
    change_str = f"{quote.change_pct * 100:+.2f}%" if quote else "未知"
    high_str = f"{quote.high:.2f}" if quote and quote.high else "未知"
    low_str = f"{quote.low:.2f}" if quote and quote.low else "未知"

    fin_section = f"""
【财务数据】
{fin_data_str}"""
    if not fin_data_str:
        fin_section = ""

    return f"""请基于以下信息对 {stock_code}（{stock_name}）进行深度选股分析：

【市场状态】
- 整体市场：{market_state_cn}
- 市场快照时间：{market_snapshot.timestamp}
- 市场快照ID：{market_snapshot.snapshot_id}

【实时行情】
- 当前价格：{price_str}
- 今日最高：{high_str}
- 今日最低：{low_str}
- 今日涨跌幅：{change_str}

【综合评分（8因子模型）】
- 综合评分：{score}/100
- 趋势强度：{trend_strength}（越高越强）
- 成交量信号：{volume_signal}
- 波动率调整收益：{volatility}
- 动量评分：{momentum}
- 估值评分：{valuation_score}
- 盈利能力评分：{profitability_score}
- 成长性评分：{growth_score}
- 评分说明：{score_reason}
{fin_section}
请给出具体的选股操作建议，包括买入区间、目标价、止损位和仓位建议。"""


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_cache: dict[str, CacheEntry] = {}
_cache_lock = Lock()


def _cache_key(stock_code: str, snapshot_id: str) -> str:
    return f"ai_decision:{stock_code}:{snapshot_id}"


def _get_cached(key: str) -> Optional[AIRecommendation]:
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if not entry:
            return None
        if now - entry.created_at > CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        return entry.response


def _store_cache(key: str, response: AIRecommendation) -> None:
    with _cache_lock:
        _cache[key] = CacheEntry(response=response, created_at=time.time())


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def get_ai_recommendation(
    stock_code: str,
    stock_name: str,
    score: float,
    score_reason: str,
    market_snapshot: MarketSnapshot,
    trend_strength: float = 0.5,
    volume_signal: float = 0.5,
    volatility: float = 0.5,
    momentum: float = 0.5,
    # New params
    valuation_score: float = 0.5,
    profitability_score: float = 0.5,
    growth_score: float = 0.5,
    financial_data_str: str = "",
) -> AIRecommendation:
    """Get AI recommendation for a single stock with full context.

    Now includes financial data and produces actionable trading guidance
    (entry price range, target price, stop-loss, position sizing).
    Uses caching by (stock_code, snapshot_id).
    """
    key = _cache_key(stock_code, market_snapshot.snapshot_id)
    cached = _get_cached(key)
    if cached is not None:
        return cached

    user_prompt = _build_user_prompt(
        stock_code=stock_code,
        stock_name=stock_name,
        score=score,
        score_reason=score_reason,
        market_snapshot=market_snapshot,
        trend_strength=trend_strength,
        volume_signal=volume_signal,
        volatility=volatility,
        momentum=momentum,
        fin_data_str=financial_data_str,
        valuation_score=valuation_score,
        profitability_score=profitability_score,
        growth_score=growth_score,
    )

    response = _call_ai_with_fallback(user_prompt, market_snapshot.snapshot_id, stock_code)
    _store_cache(key, response)
    return response


def _call_ai_with_fallback(raw_text: str, snapshot_id: str, stock_code: str) -> AIRecommendation:
    """Call the AI model and parse the response, with fallback on error."""
    try:
        raw = call_ai_model(system_prompt=SYSTEM_PROMPT, user_prompt=raw_text)
        return _parse_response(raw, snapshot_id, stock_code)
    except Exception as e:
        logger.error("AI decision call failed: %s", e)
        return _fallback_response(snapshot_id, stock_code)


def _parse_response(raw_text: str, snapshot_id: str, stock_code: str) -> AIRecommendation:
    try:
        text = raw_text.strip()
        if text.startswith("```"):
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                text = text[start : end + 1]
        data = json.loads(text)

        decision = data.get("decision", "观望")
        if decision not in ("推荐", "观望", "不推荐"):
            decision = "观望"

        risk_level = data.get("risk_level", "Medium")
        if risk_level not in ("Low", "Medium", "High"):
            risk_level = "Medium"

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        alternatives = data.get("alternatives", [])
        if not isinstance(alternatives, list):
            alternatives = []

        # Parse new fields with validation
        entry_range = data.get("entry_price_range")
        if entry_range is not None and isinstance(entry_range, list) and len(entry_range) == 2:
            entry_range = [float(entry_range[0]), float(entry_range[1])]
        else:
            entry_range = None

        target_price = data.get("target_price")
        if target_price is not None:
            target_price = float(target_price)

        stop_loss = data.get("stop_loss_price") or data.get("stop_loss")
        if stop_loss is not None:
            stop_loss = float(stop_loss)

        position_ratio = data.get("position_ratio")
        if position_ratio is not None:
            position_ratio = max(0.0, min(1.0, float(position_ratio)))

        position_suggestion = data.get("position_suggestion") or (
            f"建议仓位{position_ratio * 100:.0f}%" if position_ratio is not None else None
        )

        return AIRecommendation(
            decision=decision,
            reasoning=data.get("reasoning", "暂无分析"),
            risk_level=risk_level,
            confidence=confidence,
            alternatives=alternatives[:3],
            snapshot_id=snapshot_id,
            stock_code=stock_code,
            entry_price_range=entry_range,
            target_price=target_price,
            stop_loss_price=stop_loss,
            position_suggestion=position_suggestion,
            position_ratio=position_ratio,
            financial_summary=data.get("financial_summary"),
            trading_plan=data.get("trading_plan"),
        )
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("AI decision parse failed: %s; raw=%s", e, raw_text[:200])
        return _fallback_response(snapshot_id, stock_code)


def _fallback_response(snapshot_id: str, stock_code: str) -> AIRecommendation:
    return AIRecommendation(
        decision="观望",
        reasoning="AI研判服务暂时不可用，建议结合其他分析工具综合判断。",
        risk_level="Medium",
        confidence=0.3,
        alternatives=[],
        snapshot_id=snapshot_id,
        stock_code=stock_code,
    )


def invalidate_cache(stock_code: str, snapshot_id: str) -> None:
    """Clear cached recommendation for a stock (e.g., after manual refresh)."""
    key = _cache_key(stock_code, snapshot_id)
    with _cache_lock:
        _cache.pop(key, None)


def format_financial_data_for_prompt(
    fin_metrics,
) -> str:
    """Format FinancialMetrics into a concise string for AI prompt context."""
    if not fin_metrics:
        return ""
    parts = []
    if fin_metrics.pe_ttm is not None:
        parts.append(f"市盈率(PE/TTM): {fin_metrics.pe_ttm:.1f}")
    if fin_metrics.pb is not None:
        parts.append(f"市净率(PB): {fin_metrics.pb:.2f}")
    if fin_metrics.roe is not None:
        parts.append(f"ROE: {fin_metrics.roe:.1f}%")
    if fin_metrics.net_profit_margin is not None:
        parts.append(f"净利率: {fin_metrics.net_profit_margin:.1f}%")
    if fin_metrics.gross_margin is not None:
        parts.append(f"毛利率: {fin_metrics.gross_margin:.1f}%")
    if fin_metrics.revenue_growth is not None:
        parts.append(f"营收增长率: {fin_metrics.revenue_growth:.1f}%")
    if fin_metrics.net_profit_growth is not None:
        parts.append(f"净利润增长率: {fin_metrics.net_profit_growth:.1f}%")
    if fin_metrics.debt_ratio is not None:
        parts.append(f"资产负债率: {fin_metrics.debt_ratio:.1f}%")
    if fin_metrics.eps is not None:
        parts.append(f"每股收益: {fin_metrics.eps:.2f}")
    return "；".join(parts) if parts else "暂无财务数据"