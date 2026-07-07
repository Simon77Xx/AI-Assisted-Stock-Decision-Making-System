"""Shared in-process state for backtest/AI consistency checks.

Stores the full BacktestSnapshot from the most recent backtest run.
All AI analysis must originate from this snapshot — no client-side recomputation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Optional


@dataclass(frozen=True)
class BacktestSnapshot:
    """Immutable snapshot of the most recent backtest result.

    This is the SINGLE source of truth for all AI analysis inputs.
    Every field must be computed server-side from the backtest DataFrames.
    """
    version_id: str
    created_at: str
    stock_code: str
    params: dict[str, Any]
    params_hash: str

    # Core indicators (computed by backtest engine)
    current_price: float
    ma5: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    ma_cross_status: str = "无明显交叉"
    cross_date: Optional[str] = None
    trend_filter_status: str = "震荡市"
    return_5d: float = 0.0
    return_20d: float = 0.0
    volume_ratio: float = 1.0
    current_position: str = "空仓"
    current_signal: str = "持有"
    max_drawdown: Optional[float] = None

    # Position state machine
    position_state: str = "FLAT"
    holding_days: int = 0

    # Abnormal data markers
    insufficient_data: bool = False
    missing_indicators: list[str] = field(default_factory=list)

    # Trade signals and warnings
    signals: list[dict] = field(default_factory=list)
    data_warnings: list[str] = field(default_factory=list)


def _compute_params_hash(params: dict[str, Any]) -> str:
    """Deterministic hash of backtest parameters."""
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


_lock = Lock()
_latest_snapshot: Optional[BacktestSnapshot] = None
_snapshots_by_version: dict[str, BacktestSnapshot] = {}


def update_latest_backtest(version: str, timestamp: str, stock_code: str) -> None:
    """Stub kept for backward compatibility — prefer update_snapshot()."""
    pass


def update_snapshot(snapshot: BacktestSnapshot) -> None:
    """Record the latest completed backtest snapshot."""
    global _latest_snapshot
    with _lock:
        _latest_snapshot = snapshot
        _snapshots_by_version[snapshot.version_id] = snapshot


def get_latest_backtest() -> Optional[BacktestSnapshot]:
    """Return the latest completed backtest snapshot."""
    with _lock:
        return _latest_snapshot


def get_snapshot_by_version(version_id: str) -> Optional[BacktestSnapshot]:
    """Look up a snapshot by its version ID."""
    with _lock:
        return _snapshots_by_version.get(version_id)