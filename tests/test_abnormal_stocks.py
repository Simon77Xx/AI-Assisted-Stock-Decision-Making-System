"""Tests for abnormal stock robustness."""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.backtest_engine import _clean_numeric_frame, check_insufficient_data, compute_signals, run_backtest


def test_insufficient_ma_data(sample_insufficient_data):
    """次新股: Less than 60 rows should flag insufficient_data with missing MA60."""
    result = check_insufficient_data(sample_insufficient_data)
    assert result["insufficient_data"] is True
    assert "MA60" in result["missing_indicators"]


def test_sufficient_ma_data(sample_signals_long):
    """Normal stock: all MAs present should not flag insufficient_data."""
    result = check_insufficient_data(sample_signals_long)
    assert result["insufficient_data"] is False


def test_insufficient_data_empty_df():
    """Empty DataFrame should not crash check_insufficient_data."""
    result = check_insufficient_data(pd.DataFrame())
    assert result["insufficient_data"] is False
    assert result["missing_indicators"] == []


def test_st_stock_nan_handling(sample_st_stock_df):
    """ST stock with NaN and Inf values should be cleaned without errors."""
    cleaned = _clean_numeric_frame(sample_st_stock_df)
    assert cleaned["close"].isna().sum() == 0, "NaN in close should be filled"
    # open may still have NaN if close source was NaN (clean_numeric only fills close)
    # but open should have no Inf values
    assert cleaned["open"].isin([np.inf, -np.inf]).sum() == 0, "Inf in open should be replaced"
    assert cleaned["close"].dtype.kind == "f", "Close should be float"


def test_st_stock_backtest_does_not_crash(sample_st_stock_df):
    """ST stock data should not crash the backtest engine."""
    signals = compute_signals(sample_st_stock_df)
    backtest = run_backtest(sample_st_stock_df, signals)
    assert backtest is not None
    assert len(backtest) > 0


def test_suspended_stock_zero_volume(sample_volume_analysis_df):
    """Stock with zero-volume days should not crash backtest."""
    signals = compute_signals(sample_volume_analysis_df)
    backtest = run_backtest(sample_volume_analysis_df, signals)
    assert backtest is not None
    assert len(backtest) > 0


def test_volume_zero_pct_check(sample_volume_analysis_df):
    """Check that zero-volume days are present."""
    zero_vol = (sample_volume_analysis_df["volume"].fillna(0) == 0).sum()
    assert zero_vol == 10, f"Expected 10 zero-volume days, got {zero_vol}"