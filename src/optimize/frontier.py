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
    # Drop duplicates before pivoting (keep last if duplicates exist)
    filt = filt.drop_duplicates(subset=["asset_i", "asset_j"], keep="last")
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
    # Try multiple solvers
    solvers = [cp.OSQP, cp.ECOS, cp.SCS]
    solved = False
    for solver in solvers:
        try:
            problem.solve(solver=solver, verbose=False, max_iters=5000, eps_abs=1e-5, eps_rel=1e-5)
            if weights.value is not None:
                solved = True
                break
        except Exception:
            continue
    
    if not solved or weights.value is None:
        # Fallback: use equal weights if optimization fails
        solution = np.ones(n) / n
        return solution
    solution = np.maximum(weights.value, 0.0)
    if solution.sum() == 0:
        solution = np.ones_like(solution) / len(solution)
    else:
        solution = solution / solution.sum()
    return solution


def run(lookback: int = DEFAULT_LOOKBACK, rebalance_freq: str = "monthly") -> OptimizationArtifacts:
    from src.common.io import read_parquet, write_dataset
    from src.common.schemas import enforce_schema

    returns = read_parquet("features/returns/dt=*/*.parquet")
    covariances = read_parquet("features/covariances/dt=*/*.parquet")
    if returns.empty or covariances.empty:
        return OptimizationArtifacts(
            weights=pd.DataFrame(columns=["dt", "asset_id", "weight"]),
            stats=pd.DataFrame(columns=["dt", "expected_return", "volatility"]),
        )

    returns = returns.copy()
    returns["dt"] = pd.to_datetime(returns["dt"])
    returns = returns.sort_values("dt")
    
    # Determine rebalance dates
    if rebalance_freq == "monthly":
        # Rebalance on first trading day of each month
        rebalance_dates = returns.groupby([returns["dt"].dt.year, returns["dt"].dt.month])["dt"].first().values
    elif rebalance_freq == "quarterly":
        # Rebalance on first trading day of each quarter
        rebalance_dates = returns.groupby([returns["dt"].dt.year, returns["dt"].dt.quarter])["dt"].first().values
    else:
        # Default: use latest date only
        rebalance_dates = [returns["dt"].max()]

    all_weights = []
    all_stats = []
    
    for rebalance_dt in rebalance_dates:
        rebalance_dt_str = pd.to_datetime(rebalance_dt).strftime("%Y-%m-%d")
        try:
            expected = _expected_returns(returns, rebalance_dt_str, lookback=lookback)
            assets = sorted(expected.index.tolist())
            if len(assets) == 0:
                continue
            cov_matrix = _covariance_matrix(covariances, rebalance_dt_str, assets)
            solution = _solve_mean_variance(expected.reindex(assets), cov_matrix)

            weights_df = pd.DataFrame({"asset_id": assets, "weight": solution})
            weights_df["dt"] = rebalance_dt_str
            all_weights.append(weights_df)

            expected_return = float(np.dot(solution, expected.reindex(assets).values))
            volatility = float(np.sqrt(solution @ cov_matrix @ solution))
            all_stats.append({
                "dt": rebalance_dt_str,
                "expected_return": expected_return,
                "volatility": volatility,
            })
        except Exception as e:
            # Skip this date if optimization fails
            continue

    if not all_weights:
        return OptimizationArtifacts(
            weights=pd.DataFrame(columns=["dt", "asset_id", "weight"]),
            stats=pd.DataFrame(columns=["dt", "expected_return", "volatility"]),
        )

    weights_df = pd.concat(all_weights, ignore_index=True)
    weights_df = enforce_schema(weights_df, "src/contracts/gold_portfolios.json")
    write_dataset(weights_df, "gold/portfolios", partition_cols=("dt",))

    stats_df = pd.DataFrame(all_stats)
    stats_df = enforce_schema(stats_df, "src/contracts/gold_portfolio_stats.json")
    write_dataset(stats_df, "gold/portfolio_stats", partition_cols=("dt",))

    return OptimizationArtifacts(weights=weights_df, stats=stats_df)


if __name__ == "__main__":
    run()
