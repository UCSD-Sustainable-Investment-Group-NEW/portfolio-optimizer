from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence

import cvxpy as cp
import numpy as np
import pandas as pd

DEFAULT_LOOKBACK = int(os.getenv("EXPECTED_RETURN_LOOKBACK", "20"))
RISK_AVERSION = float(os.getenv("RISK_AVERSION", "5.0"))
WEIGHT_CAP = float(os.getenv("WEIGHT_CAP", "0.07"))


@dataclass
class OptimizationArtifacts:
    weights: pd.DataFrame
    stats: pd.DataFrame


def _latest_dt(values: pd.Series) -> str:
    if values.empty:
        raise ValueError("No dates available")
    latest = pd.to_datetime(values).max()
    return latest.strftime("%Y-%m-%d")


def _expected_returns(returns: pd.DataFrame, dt: str, lookback: int) -> pd.Series:
    returns = returns.copy()
    returns["dt"] = pd.to_datetime(returns["dt"])
    cutoff = pd.to_datetime(dt) - pd.Timedelta(days=lookback - 1)
    window = returns.loc[(returns["dt"] <= pd.to_datetime(dt)) & (returns["dt"] >= cutoff)]
    if window.empty:
        window = returns.loc[returns["dt"] <= pd.to_datetime(dt)]
    expected = window.groupby("asset_id")["return_1d"].mean()
    return expected.fillna(0.0)


def _covariance_matrix(covariances: pd.DataFrame, dt: str, assets: Sequence[str]) -> np.ndarray:
    filt = covariances[covariances["dt"] == dt]
    if filt.empty:
        raise ValueError(f"No covariance matrix available for {dt}")
    pivot = filt.pivot(index="asset_i", columns="asset_j", values="cov").reindex(index=assets, columns=assets)
    pivot = pivot.fillna(0.0)
    sym = (pivot.values + pivot.values.T) / 2.0
    np.fill_diagonal(sym, np.maximum(np.diag(sym), 1e-6))
    return sym


def _solve_mean_variance(expected: pd.Series, cov_matrix: np.ndarray) -> np.ndarray:
    assets = expected.index.tolist()
    n = len(assets)
    if n == 0:
        return np.array([])
    mu = expected.values
    Sigma = cov_matrix
    weights = cp.Variable(n)
    objective = cp.Maximize(mu @ weights - RISK_AVERSION * cp.quad_form(weights, Sigma))
    constraints = [
        cp.sum(weights) == 1.0,
        weights >= 0,
        weights <= WEIGHT_CAP,
    ]
    problem = cp.Problem(objective, constraints)
    problem.solve(solver=cp.SCS, verbose=False, max_iters=2500)
    if weights.value is None:
        raise RuntimeError("Optimization failed to converge")
    solution = np.maximum(weights.value, 0.0)
    if solution.sum() == 0:
        solution = np.ones_like(solution) / len(solution)
    else:
        solution = solution / solution.sum()
    return solution


def run(lookback: int = DEFAULT_LOOKBACK) -> OptimizationArtifacts:
    from src.common.io import read_parquet, write_dataset
    from src.common.schemas import enforce_schema

    returns = read_parquet("features/returns/dt=*/part*.parquet")
    covariances = read_parquet("features/covariances/dt=*/part*.parquet")
    if returns.empty or covariances.empty:
        return OptimizationArtifacts(
            weights=pd.DataFrame(columns=["dt", "asset_id", "weight"]),
            stats=pd.DataFrame(columns=["dt", "expected_return", "volatility"]),
        )

    latest_dt = _latest_dt(returns["dt"])
    expected = _expected_returns(returns, latest_dt, lookback=lookback)
    assets = sorted(expected.index.tolist())
    cov_matrix = _covariance_matrix(covariances, latest_dt, assets)
    solution = _solve_mean_variance(expected.reindex(assets), cov_matrix)

    weights_df = pd.DataFrame({"asset_id": assets, "weight": solution})
    weights_df["dt"] = latest_dt
    weights_df = enforce_schema(weights_df, "src/contracts/gold_portfolios.json")
    write_dataset(weights_df, "gold/portfolios", partition_cols=("dt",))

    expected_return = float(np.dot(solution, expected.reindex(assets).values))
    volatility = float(np.sqrt(solution @ cov_matrix @ solution))
    stats_df = pd.DataFrame(
        [
            {
                "dt": latest_dt,
                "expected_return": expected_return,
                "volatility": volatility,
            }
        ]
    )
    stats_df = enforce_schema(stats_df, "src/contracts/gold_portfolio_stats.json")
    write_dataset(stats_df, "gold/portfolio_stats", partition_cols=("dt",))

    return OptimizationArtifacts(weights=weights_df, stats=stats_df)


if __name__ == "__main__":
    run()
