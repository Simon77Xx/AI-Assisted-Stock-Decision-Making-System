"""AI judgement business logic with prompt building, cache and response parsing."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Optional

from pydantic import BaseModel, Field

from judgement.client import call_ai_model

logger = logging.getLogger(__name__)
CACHE_TTL_SECONDS = 300


class IndicatorInput(BaseModel):
    """Structured indicators produced by the latest completed backtest.

    All fields must be populated from the BacktestSnapshot — no client-side recomputation.
    """

    stock_code: str = Field(..., description="Stock code")
    stock_name: Optional[str] = Field(default="", description="Stock name")
    current_price: float = Field(..., description="Current price")
    ma5: Optional[float] = Field(default=None, description="MA5")
    ma20: Optional[float] = Field(default=None, description="MA20")
    ma60: Optional[float] = Field(default=None, description="MA60")
    ma_cross_status: str = Field(..., description="MA cross status")
    cross_date: Optional[str] = Field(default=None, description="Latest cross date")
    trend_filter_status: str = Field(..., description="Trend filter status")
    return_5d: float = Field(..., description="5-day return")
    return_20d: float = Field(..., description="20-day return")
    volume_ratio: float = Field(default=1.0, description="Volume ratio")
    current_position: str = Field(..., description="Position status")
    current_signal: str = Field(default="持有", description="Mechanical strategy signal")
    max_drawdown: Optional[float] = Field(default=None, description="Recent max drawdown")
    backtest_version: str = Field(..., description="Backtest version used by this request")
    backtest_timestamp: Optional[str] = Field(default=None, description="Backtest completion time")
    data_warnings: list[str] = Field(default_factory=list, description="Data quality notes")

    # Position state machine (from BacktestSnapshot)
    position_state: str = Field(default="FLAT", description="Current position state: FLAT/LONG")
    holding_days: int = Field(default=0, description="Consecutive days in current position")
    insufficient_data: bool = Field(default=False, description="Whether MA data is insufficient")
    missing_indicators: list[str] = Field(default_factory=list, description="Missing MA indicators")


class AISummaryResponse(BaseModel):
    """Structured AI judgement response."""

    judgment: str = Field(..., description="看多/看空/中性")
    confidence: str = Field(..., description="高/中/低")
    reasons: list[str] = Field(..., description="Reason list")
    risk_note: str = Field(
        default="以上判断仅基于历史技术指标的辅助参考，不构成投资建议，市场存在不确定性，请结合自身判断谨慎决策。",
        description="Risk note",
    )
    cached: bool = Field(default=False, description="Whether response came from memory cache")
    cacheAgeSeconds: Optional[int] = Field(default=None, description="Cache age in seconds")
    backtestVersion: str = Field(default="", description="Backtest version used")

    # AI explainability fields
    strategy_alignment: str = Field(default="", description="一致/不一致 — whether AI agrees with mechanical strategy")
    explanation: str = Field(default="", description="Natural language explanation of alignment or divergence")


@dataclass
class CacheEntry:
    response: AISummaryResponse
    created_at: float


_cache: dict[str, CacheEntry] = {}
_cache_lock = Lock()
_request_locks: dict[str, Lock] = {}
_request_locks_lock = Lock()

SYSTEM_PROMPT = """你是一位专业的A股技术分析顾问。你只能基于用户提供的、已经由最近一次成功回测计算完成的结构化指标进行分析。

核心约束：
1. 不得重新计算指标，不得假设、推断或编造任何未提供的数据。
2. 机械策略信号和AI观点是两类信息：机械策略来自规则，AI观点来自综合技术判断。两者可能一致，也可能分歧。
3. 用户会提供 Current Strategy Signal, Current Position State, Recent MA Trend, Volume Trend。请分析AI观点为什么与机械策略一致或不一致。
4. 输出必须是纯 JSON，不要包含代码块或额外说明。

JSON 格式：
{
  "judgment": "看多",
  "confidence": "中",
  "reasons": ["理由1", "理由2", "理由3"],
  "risk_note": "以上判断仅基于历史技术指标的辅助参考，不构成投资建议，市场存在不确定性，请结合自身判断谨慎决策。",
  "strategy_alignment": "一致",
  "explanation": "使用自然语言解释AI判断与机械策略信号一致或分歧的原因"
}

字段约束：
- judgment 只能是 "看多" / "看空" / "中性"
- confidence 只能是 "高" / "中" / "低"
- reasons 包含 2-4 条简洁理由，每条一句话
- strategy_alignment 只能是 "一致" / "不一致"（必填）
- explanation 是自然语言解释，长度不限（必填）
"""


def _fmt_value(value: Optional[float], label: str) -> str:
    if value is None:
        return f"{label} unavailable"
    return f"{value:.4f}"


def _build_user_prompt(indicators: IndicatorInput) -> str:
    r5d = f"{indicators.return_5d * 100:.1f}%"
    r20d = f"{indicators.return_20d * 100:.1f}%"
    mdd = f"{indicators.max_drawdown * 100:.1f}%" if indicators.max_drawdown is not None else "暂无数据"
    cross_info = (
        f"最近一次{indicators.ma_cross_status}（{indicators.cross_date}）"
        if indicators.cross_date
        else indicators.ma_cross_status
    )
    warnings = "；".join(indicators.data_warnings) if indicators.data_warnings else "无"

    # Volume trend description
    vol_trend = "高于" if indicators.volume_ratio > 1.1 else "低于" if indicators.volume_ratio < 0.9 else "接近"

    # MA trend description
    ma_trend_parts = []
    if indicators.ma5 is not None and indicators.ma20 is not None:
        if indicators.ma5 > indicators.ma20:
            ma_trend_parts.append(f"MA5({indicators.ma5:.2f}) > MA20({indicators.ma20:.2f}) — bullish")
        else:
            ma_trend_parts.append(f"MA5({indicators.ma5:.2f}) < MA20({indicators.ma20:.2f}) — bearish")
    if indicators.ma60 is not None:
        ma_trend_parts.append(f"MA60 = {indicators.ma60:.2f}")
    ma_trend_str = "；".join(ma_trend_parts) if ma_trend_parts else "暂无数据"

    # Position state
    pos_info = f"{indicators.position_state}（已连续 {indicators.holding_days} 个交易日）"
    if indicators.insufficient_data:
        pos_info += f"\n⚠️ 数据不完整，缺失指标：{'、'.join(indicators.missing_indicators)}"

    return f"""请基于以下最近一次成功回测结果对 {indicators.stock_code}（{indicators.stock_name or '未知'}）进行市场研判：

Backtest Version: {indicators.backtest_version}
Backtest Completed At: {indicators.backtest_timestamp or 'unknown'}

【价格信息】
- 当前价格：{indicators.current_price:.4f}
- MA5：{_fmt_value(indicators.ma5, 'MA5')}
- MA20：{_fmt_value(indicators.ma20, 'MA20')}
- MA60：{_fmt_value(indicators.ma60, 'MA60')}

【均线信号】
- 金叉/死叉状态：{cross_info}
- 趋势过滤器判定：{indicators.trend_filter_status}

【近期表现】
- 近5日涨跌幅：{r5d}
- 近20日涨跌幅：{r20d}
- 量比：{indicators.volume_ratio:.2f}（{vol_trend}20日均量）

【策略与风险】
- Current Strategy Signal: {indicators.current_signal}
- Current Position State: {pos_info}
- Current MA Trend: {ma_trend_str}
- Volume Trend: {vol_trend} 20日均量
- 近期最大回撤：{mdd}
- 数据说明：{warnings}

请明确说明AI观点与 Current Strategy Signal 是一致还是存在分歧，并解释原因。"""


def _parse_response(raw_text: str, backtest_version: str) -> AISummaryResponse:
    try:
        text = raw_text.strip()
        if text.startswith("```"):
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                text = text[start : end + 1]
        data = json.loads(text)
        response = AISummaryResponse(**data)
        response.backtestVersion = backtest_version
        return response
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("AI response parse failed: %s; raw=%s", e, raw_text[:200])
        return _fallback_response("AI研判暂不可用，请稍后重试", backtest_version)


def _fallback_response(reason: str, backtest_version: str) -> AISummaryResponse:
    return AISummaryResponse(
        judgment="中性",
        confidence="低",
        reasons=[reason],
        risk_note="以上判断仅基于历史技术指标的辅助参考，不构成投资建议，市场存在不确定性，请结合自身判断谨慎决策。",
        backtestVersion=backtest_version,
    )


def _cache_key(indicators: IndicatorInput) -> str:
    return f"{indicators.stock_code}:{indicators.backtest_version}"


def _get_cached(key: str) -> AISummaryResponse | None:
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if not entry:
            return None
        age = now - entry.created_at
        if age > CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        cached = entry.response.model_copy(deep=True)
        cached.cached = True
        cached.cacheAgeSeconds = int(age)
        return cached


def _store_cache(key: str, response: AISummaryResponse) -> None:
    clean_response = response.model_copy(deep=True)
    clean_response.cached = False
    clean_response.cacheAgeSeconds = None
    with _cache_lock:
        _cache[key] = CacheEntry(response=clean_response, created_at=time.time())


def _get_per_key_lock(key: str) -> Lock:
    """Get or create a per-key lock for request deduplication."""
    with _request_locks_lock:
        if key not in _request_locks:
            _request_locks[key] = Lock()
        return _request_locks[key]


def get_ai_judgement(indicators: IndicatorInput) -> AISummaryResponse:
    """Return AI judgement with memory cache and per-key duplicate request lock."""
    key = _cache_key(indicators)
    cached = _get_cached(key)
    if cached:
        return cached

    lock = _get_per_key_lock(key)
    if not lock.acquire(blocking=False):
        cached = _get_cached(key)
        if cached:
            return cached
        raise RuntimeError("AI analysis is already running. Please wait.")

    try:
        cached = _get_cached(key)
        if cached:
            return cached
        user_prompt = _build_user_prompt(indicators)
        raw_response = call_ai_model(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
        response = _parse_response(raw_response, indicators.backtest_version)
        _store_cache(key, response)
        return response
    except (ConnectionError, TimeoutError, RuntimeError) as e:
        logger.error("AI judgement call failed: %s", e)
        return _fallback_response(f"AI研判服务暂时不可用（{str(e)[:50]}），请稍后重试", indicators.backtest_version)
    except Exception as e:
        logger.exception("Unexpected AI judgement error: %s", e)
        return _fallback_response("AI研判服务异常，请稍后重试", indicators.backtest_version)
    finally:
        lock.release()
