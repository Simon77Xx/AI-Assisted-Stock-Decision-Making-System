"""AI Decision Service — enhanced AI selection + explanation layer.

Builds on the existing judgement service with:
- Market state context (bull/bear/sideways)
- Stock score (0-100) from scoring engine
- Structured output: decision, reasoning, risk_level, confidence, alternatives
- Prohibition on absolute predictions (must use probabilities/risk/conditions)
- Caching by snapshot_id + stock_code with 5-min TTL
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Optional

from judgement.client import call_ai_model
from market_service import MarketSnapshot

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AIRecommendation:
    """Structured AI recommendation output."""

    decision: str  # "推荐" | "观望" | "不推荐"
    reasoning: str
    risk_level: str  # "Low" | "Medium" | "High"
    confidence: float  # 0.0 – 1.0
    alternatives: list[str]  # Top 3 alternative stock codes
    snapshot_id: str
    stock_code: str


@dataclass
class CacheEntry:
    response: AIRecommendation
    created_at: float


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """你是一位专业的A股技术分析顾问。你的任务是辅助选股，而非给出确定性建议。

核心约束：
1. 你必须基于提供的市场状态、股票评分和技术指标进行分析。
2. 禁止使用"必涨"、"必跌"、"稳赚"、"绝对"等确定性词汇。
3. 必须使用概率性语言、风险判断和条件性分析。
4. 输出必须是纯 JSON，不要包含额外的解释或 markdown 代码块。
5. 风险等级根据技术指标合理评估。

JSON 输出格式：
{
  "decision": "推荐/观望/不推荐",
  "reasoning": "用一两句话说明主要理由（新手友好，避免专业术语堆砌）",
  "risk_level": "Low/Medium/High",
  "confidence": 0.75,
  "alternatives": ["替代股票代码1", "替代股票代码2", "替代股票代码3"]
}

字段约束：
- decision 只能是 "推荐" / "观望" / "不推荐"
- reasoning 必须使用简单易懂的中文，避免 MA/RSI 等术语堆砌
- risk_level 只能是 "Low" / "Medium" / "High"
- confidence 是 0.0-1.0 之间的浮点数
- alternatives 最多3个替代股票代码（可以少于3个）
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
) -> str:
    """Build the user prompt with full context for AI analysis."""
    market_state_cn = {
        "bull": "牛市",
        "bear": "熊市",
        "sideways": "震荡市",
        "unknown": "未知",
    }.get(market_snapshot.market_state, market_snapshot.market_state)

    quote = market_snapshot.stock_data_map.get(stock_code)
    price_str = f"{quote.price:.2f}" if quote else "未知"
    change_str = f"{quote.change_pct * 100:+.2f}%" if quote else "未知"

    return f"""请基于以下信息对 {stock_code}（{stock_name}）进行选股分析：

【市场状态】
- 整体市场：{market_state_cn}
- 市场快照时间：{market_snapshot.timestamp}
- 市场快照ID：{market_snapshot.snapshot_id}

【实时行情】
- 当前价格：{price_str}
- 今日涨跌幅：{change_str}

【股票评分】
- 综合评分：{score}/100
- 趋势强度：{trend_strength}
- 成交量信号：{volume_signal}
- 波动率调整收益：{volatility}
- 动量评分：{momentum}
- 评分说明：{score_reason}

请给出选股建议。"""


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
) -> AIRecommendation:
    """Get AI recommendation for a single stock.

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
        # Validate decision
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

        return AIRecommendation(
            decision=decision,
            reasoning=data.get("reasoning", "暂无分析"),
            risk_level=risk_level,
            confidence=confidence,
            alternatives=alternatives[:3],
            snapshot_id=snapshot_id,
            stock_code=stock_code,
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