"""Shared test fixtures for backtest tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_signals_long() -> pd.DataFrame:
    """A signals DataFrame ending in a LONG position with known holding days."""
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    np.random.seed(42)
    close = 10 + np.cumsum(np.random.randn(30) * 0.1)
    ma5 = pd.Series(close).rolling(5, min_periods=1).mean()
    ma20 = pd.Series(close).rolling(20, min_periods=1).mean()
    ma60 = pd.Series(close).rolling(60, min_periods=1).mean()

    data = {
        "date": dates,
        "close": close,
        "MA5": ma5,
        "MA20": ma20,
        "MA60": ma60,
        "raw_signal": 0,
        "signal": 0,
        "position": 0,
    }
    df = pd.DataFrame(data)

    # Simulate golden cross at day 15 -> LONG
    df.loc[15:, "raw_signal"] = 1
    df.loc[15:, "signal"] = 1
    df.loc[15:, "position"] = 1
    # First 15 days remain FLAT
    df.loc[:14, "position"] = 0
    return df


@pytest.fixture
def sample_signals_flat() -> pd.DataFrame:
    """A signals DataFrame ending in FLAT."""
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    close = 10 + np.cumsum(np.random.randn(30) * 0.1)
    ma5 = pd.Series(close).rolling(5, min_periods=1).mean()
    ma20 = pd.Series(close).rolling(20, min_periods=1).mean()
    ma60 = pd.Series(close).rolling(60, min_periods=1).mean()

    data = {
        "date": dates,
        "close": close,
        "MA5": ma5,
        "MA20": ma20,
        "MA60": ma60,
        "raw_signal": 0,
        "signal": 0,
        "position": 0,
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_insufficient_data() -> pd.DataFrame:
    """Signals with insufficient data for MA60 (less than 60 rows)."""
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    close = 10 + np.cumsum(np.random.randn(30) * 0.1)
    ma5 = pd.Series(close).rolling(5, min_periods=1).mean()
    ma20 = pd.Series(close).rolling(20, min_periods=1).mean()
    # MA60 will be all NaN since < 60 rows

    return pd.DataFrame({
        "date": dates,
        "close": close,
        "MA5": ma5,
        "MA20": ma20,
        "MA60": pd.Series([np.nan] * 30),
        "raw_signal": [0] * 30,
        "signal": [0] * 30,
        "position": [0] * 30,
    })


@pytest.fixture
def sample_st_stock_df() -> pd.DataFrame:
    """DataFrame with NaN and Inf values simulating an ST stock."""
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    np.random.seed(42)
    close = np.random.randn(10) * 0.5 + 5
    close[3] = np.nan  # Missing data

    df = pd.DataFrame({
        "date": dates,
        "open": close + np.random.randn(10) * 0.1,
        "close": close,
        "high": close + np.abs(np.random.randn(10) * 0.2),
        "low": close - np.abs(np.random.randn(10) * 0.2),
        "volume": np.random.randint(0, 1000000, 10),
    })
    df.loc[4, "close"] = np.nan
    df.loc[5, "open"] = np.inf
    return df


@pytest.fixture
def sample_volume_analysis_df() -> pd.DataFrame:
    """DataFrame with zero-volume days simulating a suspended stock."""
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    close = 10 + np.cumsum(np.random.randn(50) * 0.1)
    volume = np.random.randint(100000, 1000000, 50)
    # 10 zero-volume days (suspension)
    volume[10:20] = 0

    return pd.DataFrame({
        "date": dates,
        "open": close + np.random.randn(50) * 0.1,
        "close": close,
        "high": close + np.abs(np.random.randn(50) * 0.2),
        "low": close - np.abs(np.random.randn(50) * 0.2),
        "volume": volume,
    })