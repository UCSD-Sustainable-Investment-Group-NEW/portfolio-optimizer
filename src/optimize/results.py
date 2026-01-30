from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

import cvxpy as cp
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

# -------------------------------------------------------------------
# Data Models
# -------------------------------------------------------------------

class SharpeDate(BaseModel):
    date: str
    sharpe: float

class FrontierPoint(BaseModel):
    target_esg: float
    sharpe: float

class AssetHolding(BaseModel):
    ticker: str
    weight: float
    sector: Optional[str] = None
    esg_score: float
    name: Optional[str] = None
    sharpe: float

class PortfolioMetrics(BaseModel):
    expected_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float

class OptimizationResult(BaseModel):
    last_updated: str
    constraints: Dict
    metrics: PortfolioMetrics
    holdings: List[AssetHolding]
    frontier: List[FrontierPoint]
    rolling_sharpes: List[SharpeDate]
    sharpe: float
    tangency_sharpe: Optional[float] = None
    weights: Dict[str, float]
    assets: List[str]


# -------------------------------------------------------------------
# Logic
# -------------------------------------------------------------------

def _get_latest_date(df: pd.DataFrame) -> str:
    if df.empty:
        raise ValueError("DataFrame is empty")
    return df["dt"].max()

def _calculate_max_sharpe(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    esg_scores: Optional[pd.Series] = None,
    min_esg: Optional[float] = None,
    weight_cap: float = 0.07,
) -> Tuple[float, Optional[np.ndarray]]:
    """
    Calculates the Maximum Sharpe Ratio portfolio.
    Optional constraint: Portfolio ESG score >= min_esg.
    """
    assets = expected_returns.index.tolist()
    n = len(assets)
    mu = expected_returns.values
    Sigma = cov_matrix.values
    
    # We solve for y = w / (mu.T @ w)
    # This transforms the Max Sharpe problem into a convex QP (Minimize y.T @ Sigma @ y)
    # Constraints: sum(y) = k, mu.T @ y = 1, y >= 0
    # Then w = y / k
    
    y = cp.Variable(n)
    kappa = cp.Variable(1)
    
    # Objective: Minimize risk (scaled)
    # y^T Sigma y  corresponds to 1 / (Sharpe^2) roughly, since we fix return to 1.
    objective = cp.Minimize(cp.quad_form(y, Sigma))
    
    constraints = [
        y >= 0,
        kappa >= 0,
        mu @ y == 1,
        cp.sum(y) == kappa,
        y <= weight_cap * kappa  # Transformed weight cap: w <= Cap --> y/k <= Cap --> y <= Cap * k
    ]
    
    if esg_scores is not None and min_esg is not None:
        # Constraint: w.T @ esg >= min_esg
        # Transformed: (y/k).T @ esg >= min_esg --> y.T @ esg >= min_esg * k
        esg_vals = esg_scores.reindex(assets).fillna(0).values
        constraints.append(esg_vals @ y >= min_esg * kappa)

    problem = cp.Problem(objective, constraints)
    
    solvers = [cp.OSQP, cp.ECOS, cp.SCS]
    solved = False
    
    for solver in solvers:
        try:
            problem.solve(solver=solver, verbose=False)
            if problem.status in ["optimal", "optimal_inaccurate"] and y.value is not None and kappa.value is not None:
                solved = True
                break
        except Exception:
            continue
            
    if not solved:
        return 0.0, None
        
    k_val = kappa.value[0]
    if k_val <= 1e-6:
        return 0.0, None
            
    weights = y.value / k_val
    
    # Calculate actual metrics
    ret = np.dot(weights, mu)
    vol = np.sqrt(np.dot(weights.T, np.dot(Sigma, weights)))
    sharpe = ret / vol if vol > 1e-6 else 0.0
    
    return float(sharpe), weights

def _calculate_mean_variance_frontier_point(
    expected_returns: pd.Series, 
    cov_matrix: pd.DataFrame, 
    risk_aversion: float
) -> float:
    # Just a helper if we needed standard frontier, but we need ESG frontier
    pass


def _read_recent_parquet(glob_pattern: str, ref_date: str, days: int = 40) -> pd.DataFrame:
    from src.common.io import read_parquet
    # Naive optimization: Try to load specific dates if pattern implies dt partitioning
    # Pattern: "features/returns/dt=*/*.parquet"
    if "dt=*" not in glob_pattern:
        return read_parquet(glob_pattern)
        
    start_dt = pd.to_datetime(ref_date) - pd.Timedelta(days=days)
    end_dt = pd.to_datetime(ref_date)
    date_range = pd.date_range(start_dt, end_dt)
    
    dfs = []
    # This is a bit brute force but avoids listing the whole bucket
    # Assuming glob_pattern is like "root/dt=*/*.parquet"
    root = glob_pattern.split("/dt=*")[0]
    
    for dt in date_range:
        d_str = dt.strftime("%Y-%m-%d")
        # Try to read specific path
        # Assuming filename is also standard or we use glob inside the dt directory
        # "features/returns/dt=2025-01-01/*.parquet"
        try:
            path = f"{root}/dt={d_str}/*.parquet"
            df = read_parquet(path)
            if not df.empty:
                dfs.append(df)
        except Exception:
            # Likely path doesn't exist, ignore
            pass
            
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)

def run() -> None:
    from src.common.io import read_parquet, write_json
    
    # 1. Load Data
    
    # Latest portfolios (small enough to load all to find latest date)
    portfolios_df = read_parquet("gold/portfolios/dt=*/*.parquet")
    if portfolios_df.empty:
        print("No portfolios found.")
        return
        
    latest_dt = _get_latest_date(portfolios_df)
    latest_weights_df = portfolios_df[portfolios_df["dt"] == latest_dt].drop_duplicates(subset=["asset_id"], keep="last")
    latest_weights = latest_weights_df.set_index("asset_id")["weight"]
    
    print(f"Latest optimization date: {latest_dt}")
    
    # Performance for metrics & rolling sharpe - Needs history, maybe full is ok? 
    # Or last year. Reading full might be slow if many years.
    # Let's try full for perf, it's usually smaller than features (one row per day)
    perf_df = read_parquet("gold/performance/dt=*/*.parquet")
    
    # Features for frontier - Only need recent (lookback window + buffer)
    # Frontier lookback is ~20 days. Let's load last 40 days to be safe.
    print("Loading recent returns...")
    returns_df = _read_recent_parquet("features/returns/dt=*/*.parquet", latest_dt, days=40)
    
    print("Loading recent covariances...")
    # Covariance is heavy. Only need LATEST usually, or last few days if missing.
    # Logic below selects cov for 'latest_dt'.
    # We'll load last 5 days to find a valid matrix.
    cov_df = _read_recent_parquet("features/covariances/dt=*/*.parquet", latest_dt, days=5)
    
    print("Loading recent ESG...")
    # ESG is needed for current holdings. Last 5 days.
    esg_df = _read_recent_parquet("features/esg_normalized/dt=*/*.parquet", latest_dt, days=5)
    
    
    # Filter features to latest date available <= latest_dt
    # For simplicity, assuming optimization used data up to latest_dt
    
    # Prepare Inputs for Frontier/Metrics
    # ---------------------------------
    # Expected Returns (using same logic as frontier.py or simple mean)
    # We'll re-calculate expected returns for the current universe to be consistent
    # Using a standard lookback if not specified
    lookback = 20  # Consistent with frontier.py default
    
    returns_df["dt"] = pd.to_datetime(returns_df["dt"])
    cutoff = pd.to_datetime(latest_dt) - pd.Timedelta(days=lookback*2) # bit extra buffer
    recent_returns = returns_df[(returns_df["dt"] <= latest_dt) & (returns_df["dt"] > cutoff)]
    
    # Simple mean return for 'expected return' proxy in this context
    # Ideally should match exactly what the optimizer used, but recalculating is safer than guessing
    asset_universe = latest_weights.index.tolist() # Only assets in current portfolio?
    # Better to use universe of ALL assets that could have been selected, but let's stick to valid assets
    # Actually, for the frontier we want the full opportunity set.
    
    # Get universe from covariance matrix on that date
    cov_latest = pd.DataFrame()
    if not cov_df.empty:
        cov_latest = cov_df[cov_df["dt"] == latest_dt]
        if cov_latest.empty:
            # Fallback to last available
            last_cov_dt = cov_df["dt"].max()
            cov_latest = cov_df[cov_df["dt"] == last_cov_dt]
    
    if cov_latest.empty:
         print("No covariance data found within range.")
         return 
           
    available_assets = list(set(cov_latest["asset_i"].unique()) | set(cov_latest["asset_j"].unique()))
    available_assets = sorted([a for a in available_assets if isinstance(a, str)])
    
    # Filter Returns
    expected_returns = recent_returns[recent_returns["asset_id"].isin(available_assets)] \
        .groupby("asset_id")["return_1d"].mean().fillna(0)
    
    # Filter Covariance
    cov_latest = cov_latest.drop_duplicates(subset=["asset_i", "asset_j"], keep="last")
    cov_pivot = cov_latest.pivot(index="asset_i", columns="asset_j", values="cov")
    cov_pivot = cov_pivot.reindex(index=available_assets, columns=available_assets).fillna(0)
    # Make symmetric and PSD (add small jitter)
    cov_matrix = (cov_pivot + cov_pivot.T) / 2
    # Ensure positive semi-definite by adding small value to diagonal
    # This prevents 0 volatility issues and solver failures
    vals = cov_matrix.values
    np.fill_diagonal(vals, vals.diagonal() + 1e-6)
    cov_matrix = pd.DataFrame(vals, index=cov_matrix.index, columns=cov_matrix.columns)
    
    # ESG Scores
    esg_latest = esg_df[esg_df["dt"] <= latest_dt].sort_values("dt").groupby("asset_id").last()
    esg_scores = esg_latest["esg_normalized"].reindex(available_assets).fillna(0.5) # Default to mid if missing

    # 2. Build Result Parts
    # ---------------------
    
    # A. Metrics & Holdings
    # ---------------------
    assets = latest_weights.index.tolist()
    asset_weights = latest_weights.to_dict()
    
    # Holdings List
    holdings = []
    
    # Portfolio level stats
    # Recalculate based on held assets
    held_returns = expected_returns.reindex(assets).fillna(0)
    # Re-extract vols from regularized matrix
    held_vols = np.sqrt(np.diag(cov_matrix.reindex(index=assets, columns=assets).fillna(0)))
    
    # Asset Sharpes (individual)
    # Handle division by zero/inf
    with np.errstate(divide='ignore', invalid='ignore'):
        asset_sharpes_series = held_returns / held_vols
    asset_sharpes = asset_sharpes_series.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    
    for asset in assets:
        holdings.append(AssetHolding(
            ticker=asset,
            weight=asset_weights[asset],
            esg_score=float(esg_scores.get(asset, 0.0)),
            sharpe=float(asset_sharpes.get(asset, 0.0)),
            sector=None, # Not available yet
            name=None    # Not available yet
        ))
        
    # Portfolio Metrics (Forward looking based on current weights)
    # This might differ from 'realized' backtest metrics.
    # User likely wants these consistent with the optimization view.
    
    w_vec = np.array([asset_weights.get(a, 0) for a in available_assets])
    port_ret = np.dot(w_vec, expected_returns.values)
    port_vol = np.sqrt(np.dot(w_vec.T, np.dot(cov_matrix.values, w_vec)))
    port_sharpe = port_ret / port_vol if port_vol > 1e-6 else 0.0
    
    # Max Drawdown (Needs history)
    max_dd = 0.0
    rolling_sharpes = []
    
    if not perf_df.empty:
        perf_df = perf_df.sort_values("dt")
        # Calculate DD
        cum = (1 + perf_df["portfolio_return"]).cumprod()
        peak = cum.cummax()
        dd = (cum - peak) / peak
        max_dd = float(dd.min())
        
        # Calculate Rolling Sharpe (e.g. 6 month = 126 trading days)
        window = 126
        rolling_ret = perf_df["portfolio_return"].rolling(window).mean() * 252
        rolling_vol = perf_df["portfolio_return"].rolling(window).std() * np.sqrt(252)
        rolling_sh = (rolling_ret / rolling_vol).fillna(0)
        
        # Subsample to keep JSON size manageable (e.g. weekly)
        # Or just last N points. User asked for "List[SharpeDate]".
        # Let's take every 5th point to keep it light but detailed enough.
        
        valid_rolling = rolling_sh.dropna()
        dates = perf_df.loc[valid_rolling.index, "dt"]
        
        for d, s in zip(dates, valid_rolling):
            rolling_sharpes.append(SharpeDate(date=d if isinstance(d, str) else d.strftime("%Y-%m-%d"), sharpe=float(s)))

    metrics = PortfolioMetrics(
        expected_return=float(port_ret),
        volatility=float(port_vol),
        sharpe_ratio=float(port_sharpe),
        max_drawdown=max_dd
    )
    
    # B. Frontier (ESG vs Sharpe)
    # ---------------------------
    frontier_points = []
    
    # Tangency (Unconstrained Max Sharpe)
    tangency_sharpe, _ = _calculate_max_sharpe(expected_returns, cov_matrix, weight_cap=0.07)
    
    # ESG Frontier
    # Range from Min ESG in universe to Max ESG in universe
    min_u_esg = esg_scores.min()
    max_u_esg = esg_scores.max()
    
    # Create ~20 points
    target_esgs = np.linspace(min_u_esg, max_u_esg, 20)
    
    print(f"Generating frontier with {len(target_esgs)} points...")
    for i, target in enumerate(target_esgs):
        if i % 5 == 0:
            print(f"Solving point {i+1}/{len(target_esgs)} (Target ESG: {target:.2f})...")
        s, _ = _calculate_max_sharpe(expected_returns, cov_matrix, esg_scores, min_esg=target, weight_cap=0.07)
        if s > 0:
            frontier_points.append(FrontierPoint(target_esg=float(target), sharpe=float(s)))
    print("Frontier generation complete.")
            
    # 3. Construct Result
    # -------------------
    
    result = OptimizationResult(
        last_updated=latest_dt,
        constraints={
            "weight_cap": 0.07,
            "lookback": lookback,
            "risk_aversion": 5.0 # Implicit in base optimization
        },
        metrics=metrics,
        holdings=holdings,
        frontier=frontier_points,
        rolling_sharpes=rolling_sharpes,
        sharpe=float(port_sharpe),
        tangency_sharpe=float(tangency_sharpe),
        weights=latest_weights.to_dict(),
        assets=assets
    )
    
    # 4. Save
    # -------
    # Save as partitioned JSON to keep history
    # gold/optimization_results/dt=YYYY-MM-DD/results.json
    output_key = f"gold/optimization_results/dt={latest_dt}/results.json"
    write_json(result.dict(), output_key)
    print(f"Optimization result generated for {latest_dt} at {output_key}")

if __name__ == "__main__":
    run()
