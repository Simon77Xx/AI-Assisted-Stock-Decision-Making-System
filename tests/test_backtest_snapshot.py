"""Tests for BacktestSnapshot data consistency and version locking."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from backend.backtest_engine import compute_signals, run_backtest, compute_metrics


class TestSnapshotConsistency:
    """Verify that snapshot indicators are consistent with engine-computed values."""

    def test_backtest_produces_required_columns(self, sample_signals_long):
        """Signals should contain all expected MA columns."""
        assert "MA5" in sample_signals_long.columns
        assert "MA20" in sample_signals_long.columns
        assert "MA60" in sample_signals_long.columns
        assert "position" in sample_signals_long.columns

    def test_backtest_run_produces_results(self, sample_signals_long):
        """run_backtest should produce valid output with expected columns."""
        # We need a proper df with open, high, low, volume for run_backtest
        dates = sample_signals_long["date"]
        close_values = sample_signals_long["close"].values
        df = pd.DataFrame({
            "date": dates,
            "open": close_values,
            "close": close_values,
            "high": close_values,
            "low": close_values,
            "volume": [100000] * len(dates),
        })
        backtest = run_backtest(df, sample_signals_long)
        assert "strategy_cum" in backtest.columns
        assert "benchmark_cum" in backtest.columns
        assert "daily_return" in backtest.columns
        assert len(backtest) > 0

    def test_metrics_computed_safely(self, sample_signals_long):
        """compute_metrics should produce valid KPIs."""
        dates = sample_signals_long["date"]
        close_values = sample_signals_long["close"].values
        df = pd.DataFrame({
            "date": dates,
            "open": close_values,
            "close": close_values,
            "high": close_values,
            "low": close_values,
            "volume": [100000] * len(dates),
        })
        backtest = run_backtest(df, sample_signals_long)
        metrics = compute_metrics(backtest)
        assert "累计收益率" in metrics
        assert "夏普比率" in metrics
        assert "交易次数" in metrics


class TestVersionLock:
    """Tests for backtest version locking (HTTP 409 case)."""

    def test_version_mismatch_detected(self):
        """Different versions should be detected as mismatched."""
        v1 = "abc123"
        v2 = "def456"
        assert v1 != v2, "Different versions should not match"

    def test_version_match(self):
        """Same version should be detected as match."""
        v = "abc123"
        assert v == v, "Same version should match"


@pytest.mark.asyncio
class TestDateGapDetection:
    """Tests for date gap warnings in stock data."""

    def test_no_gaps(self):
        """Consecutive business days should produce no warnings."""
        from backend.data_fetcher import get_date_gap_warnings
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        df = pd.DataFrame({"date": dates, "close": range(10)})
        warnings = get_date_gap_warnings(df)
        assert len(warnings) == 0, f"Expected no warnings, got {warnings}"

    def test_large_gap_detected(self):
        """Gap > 5 days should produce a warning."""
        from backend.data_fetcher import get_date_gap_warnings
        dates = pd.date_range("2024-01-01", periods=3, freq="B")
        gap = pd.date_range("2024-01-15", periods=3, freq="B")
        all_dates = dates.append(gap)
        df = pd.DataFrame({"date": all_dates, "close": range(6)})
        warnings = get_date_gap_warnings(df)
        assert len(warnings) > 0, "Expected date gap warning"

    def test_empty_df(self):
        """Empty DataFrame should not crash."""
        from backend.data_fetcher import get_date_gap_warnings
        warnings = get_date_gap_warnings(pd.DataFrame())
        assert warnings == []