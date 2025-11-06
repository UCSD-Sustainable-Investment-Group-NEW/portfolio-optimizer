from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd

DEFAULT_WINDOW = int(os.getenv("COV_WINDOW_DAYS", "20"))


@dataclass
class FeatureArtifacts:
    returns: pd.DataFrame
    covariances: pd.DataFrame


def _prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return prices
    prices = prices.copy()
    prices["dt"] = pd.to_datetime(prices["dt"])
    prices = prices.sort_values(["asset_id", "dt"])
    return prices


def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    prices = _prepare_prices(prices)
    if prices.empty:
        return pd.DataFrame(columns=["asset_id", "dt", "return_1d"])
    prices["return_1d"] = (
        prices.groupby("asset_id")["adj_close"].pct_change().fillna(0.0)
    )
    returns = prices[["asset_id", "dt", "return_1d"]].copy()
    returns["dt"] = returns["dt"].dt.strftime("%Y-%m-%d")
    return returns


def compute_covariances(returns: pd.DataFrame, window: int) -> pd.DataFrame:
    if returns.empty:
        return pd.DataFrame(columns=["dt", "asset_i", "asset_j", "cov"])
    returns = returns.copy()
    returns["dt"] = pd.to_datetime(returns["dt"])
    pivot = returns.pivot(index="dt", columns="asset_id", values="return_1d").sort_index()
    cov_frames = []
    for idx in range(window - 1, len(pivot)):
        window_slice = pivot.iloc[idx - window + 1 : idx + 1]
        if window_slice.shape[0] < window:
            continue
        current_dt = pivot.index[idx]
        cov_matrix = window_slice.cov(min_periods=window // 2)
        melted = cov_matrix.stack().reset_index()
        melted.columns = ["asset_i", "asset_j", "cov"]
        melted["dt"] = current_dt.strftime("%Y-%m-%d")
        cov_frames.append(melted)
    if not cov_frames:
        return pd.DataFrame(columns=["dt", "asset_i", "asset_j", "cov"])
    covariances = pd.concat(cov_frames, ignore_index=True)
    covariances = covariances[["dt", "asset_i", "asset_j", "cov"]]
    return covariances


def run(window: int = DEFAULT_WINDOW) -> FeatureArtifacts:
    from src.common.io import read_parquet, write_dataset
    from src.common.schemas import enforce_schema

    prices = read_parquet("silver/prices/dt=*/part*.parquet")
    returns = compute_returns(prices)
    covariances = compute_covariances(returns, window=window)
    if not returns.empty:
        returns = enforce_schema(returns, "src/contracts/features_returns.json")
        write_dataset(returns, "features/returns", partition_cols=("dt",))
    if not covariances.empty:
        covariances = enforce_schema(covariances, "src/contracts/features_covariances.json")
        write_dataset(covariances, "features/covariances", partition_cols=("dt",))
    return FeatureArtifacts(returns=returns, covariances=covariances)


if __name__ == "__main__":
    run()
