"""Tests for position state machine logic in backtest_engine."""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest_engine import compute_position_state


def test_golden_cross_to_long(sample_signals_long):
    """Golden cross should result in position_state = LONG."""
    state, days = compute_position_state(sample_signals_long)
    assert state == "LONG", f"Expected LONG, got {state}"
    assert days >= 10, f"Expected holding_days >= 10, got {days}"


def test_death_cross_to_flat(sample_signals_flat):
    """Death cross (or no position) should result in position_state = FLAT."""
    # Make position 0 for last 10 rows (simulating death cross)
    df = sample_signals_flat.copy()
    state, days = compute_position_state(df)
    assert state == "FLAT", f"Expected FLAT, got {state}"
    assert days >= 20, f"Expected holding_days >= 20 for flat series, got {days}"


def test_holding_days_count():
    """Holding days should count consecutive same-position days."""
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    df = pd.DataFrame({
        "date": dates,
        "position": [0, 0, 1, 1, 1, 1, 1, 1, 1, 1],
        "close": range(10, 20),
    })
    state, days = compute_position_state(df)
    assert state == "LONG", f"Expected LONG, got {state}"
    assert days == 8, f"Expected 8 holding days, got {days}"


def test_holding_days_flat():
    """Holding days for flat position."""
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    df = pd.DataFrame({
        "date": dates,
        "position": [0, 0, 0, 0, 0],
        "close": range(5),
    })
    state, days = compute_position_state(df)
    assert state == "FLAT", f"Expected FLAT, got {state}"
    assert days == 5, f"Expected 5 holding days, got {days}"


def test_empty_signals():
    """Empty signals should gracefully return FLAT."""
    df = pd.DataFrame()
    state, days = compute_position_state(df)
    assert state == "FLAT"
    assert days == 0


def test_nan_position_values():
    """NaN position values should not crash."""
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    df = pd.DataFrame({
        "date": dates,
        "position": [np.nan, np.nan, np.nan, np.nan, np.nan],
        "close": range(5),
    })
    state, days = compute_position_state(df)
    assert state in ("FLAT", "LONG")
    assert isinstance(days, int)