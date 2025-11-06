import pandas as pd
import pytest

from src.backtest import engine
from src.features import make_returns_cov
from src.features.normalize_esg import run as normalize_esg_run
from src.optimize import frontier


def _sample_prices() -> pd.DataFrame:
    rows = []
    for asset, prices in {
        "A": [100.0, 101.0, 103.0, 102.0],
        "B": [50.0, 51.0, 50.5, 51.5],
        "C": [80.0, 79.5, 80.5, 81.0],
    }.items():
        for idx, price in enumerate(prices):
            rows.append(
                {
                    "asset_id": asset,
                    "ticker": asset,
                    "adj_close": price,
                    "adj_open": price,
                    "volume": 1000 + idx,
                    "dt": pd.Timestamp("2024-01-01") + pd.Timedelta(days=idx),
                }
            )
    df = pd.DataFrame(rows)
    df["dt"] = df["dt"].dt.strftime("%Y-%m-%d")
    return df


def test_compute_returns_and_covariances():
    prices = _sample_prices()
    returns = make_returns_cov.compute_returns(prices)
    covariances = make_returns_cov.compute_covariances(returns, window=2)

    assert not returns.empty
    assert {"asset_id", "dt", "return_1d"} <= set(returns.columns)
    assert not covariances.empty
    assert {"asset_i", "asset_j", "dt", "cov"} <= set(covariances.columns)


def test_normalize_esg_run(monkeypatch):
    sample = pd.DataFrame(
        {
            "asset_id": ["A", "B"],
            "provider": ["demo", "demo"],
            "esg_raw": [10.0, 12.0],
            "esg_z": [-0.5, 0.5],
            "dt": ["2024-01-01", "2024-01-01"],
        }
    )
    writes = {}

    monkeypatch.setattr(
        "src.features.normalize_esg.read_parquet", lambda _: sample.copy()
    )
    monkeypatch.setattr(
        "src.features.normalize_esg.write_dataset",
        lambda df, root, partition_cols=("dt",): writes.setdefault(root, df.copy()),
    )

    result = normalize_esg_run()

    assert not result.empty
    assert result["esg_percentile"].between(0, 1).all()
    assert result["esg_normalized"].between(0, 1).all()
    assert "features/esg_normalized" in writes


def test_frontier_run(monkeypatch):
    prices = _sample_prices()
    returns = make_returns_cov.compute_returns(prices)
    covariances = make_returns_cov.compute_covariances(returns, window=3)
    writes = {}

    monkeypatch.setattr(
        frontier,
        "read_parquet",
        lambda path: returns.copy()
        if "features/returns" in path
        else covariances.copy(),
    )
    monkeypatch.setattr(
        frontier,
        "write_dataset",
        lambda df, root, partition_cols=("dt",): writes.setdefault(root, df.copy()),
    )
    monkeypatch.setattr(frontier, "WEIGHT_CAP", 1.0)
    monkeypatch.setattr(frontier, "RISK_AVERSION", 1.0)

    artifacts = frontier.run(lookback=3)

    weights = artifacts.weights
    assert not weights.empty
    assert weights["weight"].sum() == pytest.approx(1.0, rel=1e-6)
    assert "gold/portfolios" in writes
    assert "gold/portfolio_stats" in writes


def test_backtest_run(monkeypatch):
    prices = _sample_prices()
    returns = make_returns_cov.compute_returns(prices)
    weights = pd.DataFrame(
        {
            "dt": ["2024-01-03"] * 3,
            "asset_id": ["A", "B", "C"],
            "weight": [0.4, 0.3, 0.3],
        }
    )
    writes = {}

    def fake_read(path):
        if "features/returns" in path:
            return returns.copy()
        return weights.copy()

    monkeypatch.setattr(engine, "read_parquet", fake_read)
    monkeypatch.setattr(
        engine,
        "write_dataset",
        lambda df, root, partition_cols=("dt",): writes.setdefault(root, df.copy()),
    )

    perf = engine.run()

    assert not perf.empty
    assert perf["dt"].is_monotonic_increasing
    assert "gold/performance" in writes
