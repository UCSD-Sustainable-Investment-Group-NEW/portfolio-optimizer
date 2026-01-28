from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import minimize


@dataclass
class FrontierPoint:
    target_esg: float
    sharpe: float


@dataclass
class OptimizationResult:
    weights: pd.Series
    sharpe: float
    target_esg: float


def fetch_price_history(tickers: Sequence[str], start: dt.date, end: dt.date) -> pd.DataFrame:
    """Download adjusted close prices for tickers."""
    price_data = {}
    for t in tickers:
        hist = yf.Ticker(t).history(start=start, end=end)
        if "Close" not in hist:
            continue
        price_data[t] = hist["Close"]
    if not price_data:
        raise ValueError("No price data returned for requested tickers")
    df = pd.DataFrame(price_data)
    df.index = df.index.date
    df = df.sort_index()
    return df.dropna(how="all")


def fetch_risk_free_rate(start: dt.date, end: dt.date) -> pd.Series:
    """Daily 3M T-bill yield (annualized) converted to daily rate."""
    rf = yf.Ticker("^IRX").history(start=start + pd.DateOffset(days=1), end=end)
    if rf.empty:
        raise ValueError("No risk-free rate data available")
    daily = (rf["Close"] / 100.0) / 252
    daily.index = daily.index.date
    return daily.sort_index()


def calc_stats(price_data: pd.DataFrame, risk_free_rate: pd.Series) -> Tuple[pd.Series, pd.DataFrame]:
    """Mean daily excess returns and covariance matrix of excess returns."""
    returns = price_data.pct_change().dropna()
    aligned_rf = risk_free_rate.reindex(returns.index).fillna(method="ffill")
    excess = returns.sub(aligned_rf, axis=0)
    return excess.mean(), excess.cov()


def portfolio_sharpe(weights: np.ndarray, mean_excess_returns: pd.Series, cov_matrix: pd.DataFrame) -> float:
    portfolio_return = float(np.dot(weights, mean_excess_returns))
    volatility = float(np.sqrt(weights.T @ cov_matrix.values @ weights))
    if volatility == 0:
        return 0.0
    return (portfolio_return / volatility) * np.sqrt(252)


def asset_sharpes(mean_excess_returns: pd.Series, cov_matrix: pd.DataFrame, tickers: Sequence[str]) -> pd.Series:
    sharpes = {}
    for ticker in tickers:
        vol = np.sqrt(cov_matrix.loc[ticker, ticker])
        if vol == 0:
            sharpes[ticker] = 0.0
        else:
            sharpes[ticker] = (mean_excess_returns[ticker] / vol) * np.sqrt(252)
    return pd.Series(sharpes)


def optimize_esg_frontier(
    mean_excess_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    esg_scores: Sequence[float],
    target_esg: float,
    min_allocation: float = 0.01,
) -> OptimizationResult:
    """Maximize Sharpe subject to weights sum to 1 and ESG target."""
    n_assets = len(mean_excess_returns)
    bounds = tuple((min_allocation, 1.0) for _ in range(n_assets))

    def objective(weights: np.ndarray) -> float:
        return -portfolio_sharpe(weights, mean_excess_returns, cov_matrix)

    esg_scores_arr = np.array(esg_scores)

    esg_span = float(esg_scores_arr.max() - esg_scores_arr.min())
    base_constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    # When all ESG scores are equal (or nearly so), the ESG constraint is collinear
    # with the sum-to-one constraint and SLSQP fails with a singular matrix.
    # In that case, skip the ESG equality and fall back to the unconstrained case.
    constraints: Sequence[dict]
    if esg_span < 1e-8:
        constraints = tuple(base_constraints)
    else:
        constraints = tuple(
            base_constraints
            + [{"type": "eq", "fun": lambda w: target_esg - float(np.dot(w, esg_scores_arr))}]
        )

    init = np.ones(n_assets) / n_assets
    result = minimize(objective, init, bounds=bounds, constraints=constraints)
    if not result.success:
        raise RuntimeError(f"Optimization failed: {result.message}")

    weights = result.x
    sharpe = portfolio_sharpe(weights, mean_excess_returns, cov_matrix)
    return OptimizationResult(weights=pd.Series(weights, index=mean_excess_returns.index), sharpe=sharpe, target_esg=target_esg)


def max_sharpe_portfolio(
    mean_excess_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    min_allocation: float = 0.01,
) -> OptimizationResult:
    """Tangency portfolio without ESG constraint."""
    n_assets = len(mean_excess_returns)
    bounds = tuple((min_allocation, 1.0) for _ in range(n_assets))

    def objective(weights: np.ndarray) -> float:
        return -portfolio_sharpe(weights, mean_excess_returns, cov_matrix)

    constraints = ({"type": "eq", "fun": lambda w: np.sum(w) - 1},)
    init = np.ones(n_assets) / n_assets
    result = minimize(objective, init, bounds=bounds, constraints=constraints)
    if not result.success:
        raise RuntimeError(f"Max Sharpe optimization failed: {result.message}")
    weights = result.x
    sharpe = portfolio_sharpe(weights, mean_excess_returns, cov_matrix)
    return OptimizationResult(weights=pd.Series(weights, index=mean_excess_returns.index), sharpe=sharpe, target_esg=float("nan"))


def frontier_points(
    mean_excess_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    esg_scores: Sequence[float],
    min_allocation: float,
    step: float = 0.01,
) -> Iterable[FrontierPoint]:
    esg_scores_arr = np.array(esg_scores)
    min_esg = float(esg_scores_arr.min())
    max_esg = float(esg_scores_arr.max())
    if max_esg - min_esg < 1e-8:
        return []
    targets = np.round(np.arange(min_esg + step, max_esg - step + 1e-9, step), 3)
    for target in targets:
        try:
            opt = optimize_esg_frontier(mean_excess_returns, cov_matrix, esg_scores_arr, target, min_allocation)
            yield FrontierPoint(target_esg=target, sharpe=opt.sharpe)
        except RuntimeError:
            continue
