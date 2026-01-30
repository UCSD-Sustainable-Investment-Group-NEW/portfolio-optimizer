from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure project root is on path so we can import src.common.io when running from frontend/
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    from src.common.io import read_parquet
    LAKE_AVAILABLE = True
except Exception:
    read_parquet = None
    LAKE_AVAILABLE = False

from esg_optimizer import (
    asset_sharpes,
    calc_stats,
    fetch_price_history,
    fetch_risk_free_rate,
    frontier_points,
    max_sharpe_portfolio,
    optimize_esg_frontier,
)

app = FastAPI(title="ESG Portfolio Optimizer API")

# Add CORS middleware to allow your React frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request Models
class ESGScoreInput(BaseModel):
    ticker: str
    esg_score: float = Field(ge=0.0, le=1.0)


class OptimizationRequest(BaseModel):
    tickers: List[str]
    esg_scores: Optional[List[ESGScoreInput]] = None  # Optional - will fetch from Yahoo if not provided
    start_date: str  # Format: YYYY-MM-DD
    end_date: str  # Format: YYYY-MM-DD
    min_allocation: float = Field(default=0.01, ge=0.0, le=1.0)
    esg_step: float = Field(default=0.01, ge=0.005, le=0.05)
    target_esg: float = Field(ge=0.0, le=1.0)


# Response Models
class SharpeDate(BaseModel):
    date: str
    sharpe: float


class FrontierPoint(BaseModel):
    target_esg: float
    sharpe: float


class AssetHolding(BaseModel):
    ticker: str
    weight: float
    sector: Optional[str] = None  # Not implemented yet
    esg_score: float
    name: Optional[str] = None  # Not implemented yet
    sharpe: float


class PortfolioMetrics(BaseModel):
    expected_return: float  # Not implemented yet - placeholder
    volatility: float  # Not implemented yet - placeholder
    sharpe_ratio: float
    max_drawdown: float  # Not implemented yet - placeholder


class OptimizationResult(BaseModel):
    last_updated: str
    constraints: Dict
    metrics: PortfolioMetrics
    holdings: List[AssetHolding]
    frontier: List[FrontierPoint]
    rolling_sharpes: List[SharpeDate]
    sharpe: float
    tangency_sharpe: Optional[float] = None  # Unconstrained max-Sharpe portfolio
    weights: Dict[str, float]
    assets: List[str]


# --- Data lake (gold) response models ---
class GoldPortfolioRow(BaseModel):
    dt: str
    asset_id: str
    weight: float


class GoldPortfolioStatsRow(BaseModel):
    dt: str
    expected_return: float
    volatility: float


class GoldPerformanceRow(BaseModel):
    dt: str
    portfolio_return: float
    cumulative_return: float


class GoldLatestResponse(BaseModel):
    """Combined response for latest gold data from the data lake."""
    as_of_dt: str
    portfolios: List[GoldPortfolioRow]
    portfolio_stats: List[GoldPortfolioStatsRow]
    performance: List[GoldPerformanceRow]
    source: str = "data_lake"


def _read_gold_df(glob_pattern: str) -> pd.DataFrame:
    """Read parquet from data lake; returns empty DataFrame if lake unavailable or no data."""
    if not LAKE_AVAILABLE or read_parquet is None:
        return pd.DataFrame()
    try:
        return read_parquet(glob_pattern)
    except Exception:
        return pd.DataFrame()


def _latest_dt_from_df(df: pd.DataFrame, dt_col: str = "dt") -> Optional[str]:
    if df.empty or dt_col not in df.columns:
        return None
    return str(df[dt_col].max())


@app.get("/api/gold/portfolios", response_model=List[GoldPortfolioRow])
async def get_gold_portfolios(
    dt_filter: Optional[str] = Query(None, alias="dt", description="Partition date (YYYY-MM-DD) or 'latest'"),
):
    """Read portfolio weights from the data lake (gold layer)."""
    df = _read_gold_df("gold/portfolios/dt=*/*.parquet")
    if df.empty:
        return []
    if dt_filter and dt_filter.lower() == "latest":
        latest = _latest_dt_from_df(df)
        if latest:
            df = df[df["dt"] == latest]
    elif dt_filter:
        df = df[df["dt"].astype(str).str.startswith(dt_filter[:10])]
    df = df.drop_duplicates()
    return [GoldPortfolioRow(dt=str(row["dt"]), asset_id=str(row["asset_id"]), weight=float(row["weight"])) for _, row in df.iterrows()]


@app.get("/api/gold/portfolio-stats", response_model=List[GoldPortfolioStatsRow])
async def get_gold_portfolio_stats(
    dt_filter: Optional[str] = Query(None, alias="dt", description="Partition date (YYYY-MM-DD) or 'latest'"),
):
    """Read portfolio stats (expected return, volatility) from the data lake (gold layer)."""
    df = _read_gold_df("gold/portfolio_stats/dt=*/*.parquet")
    if df.empty:
        return []
    if dt_filter and dt_filter.lower() == "latest":
        latest = _latest_dt_from_df(df)
        if latest:
            df = df[df["dt"] == latest]
    elif dt_filter:
        df = df[df["dt"].astype(str).str.startswith(dt_filter[:10])]
    df = df.drop_duplicates()
    return [
        GoldPortfolioStatsRow(
            dt=str(row["dt"]),
            expected_return=float(row["expected_return"]),
            volatility=float(row["volatility"]),
        )
        for _, row in df.iterrows()
    ]


@app.get("/api/gold/performance", response_model=List[GoldPerformanceRow])
async def get_gold_performance(
    dt_filter: Optional[str] = Query(None, alias="dt", description="Partition date or 'latest'"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Read backtest performance from the data lake (gold layer)."""
    df = _read_gold_df("gold/performance/dt=*/*.parquet")
    if df.empty:
        return []
    if dt_filter and dt_filter.lower() == "latest":
        latest = _latest_dt_from_df(df)
        if latest:
            df = df[df["dt"] == latest]
    elif dt_filter:
        df = df[df["dt"].astype(str).str.startswith(dt_filter[:10])]
    if start:
        df = df[df["dt"].astype(str) >= start[:10]]
    if end:
        df = df[df["dt"].astype(str) <= end[:10]]
    df = df.drop_duplicates(subset=["dt"], keep="last").sort_values("dt")
    return [
        GoldPerformanceRow(
            dt=str(row["dt"]),
            portfolio_return=float(row["portfolio_return"]),
            cumulative_return=float(row["cumulative_return"]),
        )
        for _, row in df.iterrows()
    ]


@app.get("/api/gold/latest", response_model=GoldLatestResponse)
async def get_gold_latest():
    """Return latest gold data from the data lake (portfolios, stats, performance) for the dashboard."""
    portfolios_df = _read_gold_df("gold/portfolios/dt=*/*.parquet")
    stats_df = _read_gold_df("gold/portfolio_stats/dt=*/*.parquet")
    perf_df = _read_gold_df("gold/performance/dt=*/*.parquet")

    as_of_dt = ""
    if not portfolios_df.empty and "dt" in portfolios_df.columns:
        as_of_dt = str(portfolios_df["dt"].max())
    elif not stats_df.empty and "dt" in stats_df.columns:
        as_of_dt = str(stats_df["dt"].max())
    elif not perf_df.empty and "dt" in perf_df.columns:
        as_of_dt = str(perf_df["dt"].max())

    # Latest partition only for portfolios and stats
    if not portfolios_df.empty and as_of_dt:
        portfolios_df = portfolios_df[portfolios_df["dt"].astype(str) == as_of_dt]
    if not stats_df.empty and as_of_dt:
        stats_df = stats_df[stats_df["dt"].astype(str) == as_of_dt]
    # Performance: full series (already sorted by dt in read)
    if not perf_df.empty:
        perf_df = perf_df.sort_values("dt").drop_duplicates(subset=["dt"], keep="last")

    portfolios = [
        GoldPortfolioRow(dt=str(r["dt"]), asset_id=str(r["asset_id"]), weight=float(r["weight"]))
        for _, r in portfolios_df.iterrows()
    ]
    portfolio_stats = [
        GoldPortfolioStatsRow(dt=str(r["dt"]), expected_return=float(r["expected_return"]), volatility=float(r["volatility"]))
        for _, r in stats_df.iterrows()
    ]
    performance = [
        GoldPerformanceRow(dt=str(r["dt"]), portfolio_return=float(r["portfolio_return"]), cumulative_return=float(r["cumulative_return"]))
        for _, r in perf_df.iterrows()
    ]

    return GoldLatestResponse(
        as_of_dt=as_of_dt or "",
        portfolios=portfolios,
        portfolio_stats=portfolio_stats,
        performance=performance,
        source="data_lake",
    )


def fetch_benchmark(tickers: List[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Download benchmark close prices, trying multiple symbols and fallbacks."""
    for tk in tickers:
        attempts = [
            ("range", lambda: yf.Ticker(tk).history(start=start, end=end)),
            ("10y", lambda: yf.Ticker(tk).history(period="10y")),
            ("5y", lambda: yf.Ticker(tk).history(period="5y")),
            ("3y", lambda: yf.Ticker(tk).history(period="3y")),
            ("download", lambda: yf.download(tk, start=start, end=end, progress=False)),
            ("download-5y", lambda: yf.download(tk, period="5y", progress=False)),
        ]
        for label, fetch in attempts:
            try:
                hist = fetch()
                if hist is None or hist.empty:
                    continue
                close_col = "Adj Close" if "Adj Close" in hist.columns else "Close" if "Close" in hist.columns else None
                if close_col is None:
                    continue
                close = hist[close_col]
                close.index = pd.to_datetime(close.index)
                return close.sort_index()
            except Exception:
                continue
    return pd.Series(dtype=float)


def rolling_sharpe(excess: pd.Series, window: int) -> pd.Series:
    """Calculate rolling Sharpe ratio."""
    def _fn(x: pd.Series) -> float:
        sigma = x.std()
        if sigma == 0 or np.isnan(sigma):
            return np.nan
        return x.mean() / sigma * np.sqrt(252)
    return excess.rolling(window=window, min_periods=max(60, window // 4)).apply(_fn, raw=False)


def fetch_esg_scores(tickers: List[str]) -> Dict[str, float]:
    """Fetch ESG scores from Yahoo Finance sustainability; returns mapping ticker->score in [0,1]."""
    scores = {}
    for t in tickers:
        try:
            ticker_obj = yf.Ticker(t)
            sustain = ticker_obj.sustainability
            print(f"Attempting to fetch ESG for {t}...")
            print(f"  Sustainability data: {sustain}")
            
            if sustain is None or sustain.empty:
                print(f"  No sustainability data available for {t}")
                continue
            
            # Yahoo reports totalEsg on a 0-100 scale; normalize to 0-1 range.
            if "totalEsg" in sustain.index:
                val = float(sustain.loc["totalEsg"].values[0])
                print(f"  Raw ESG value: {val}")
                if val > 1.0:
                    val = val / 100.0
                scores[t] = max(0.0, min(1.0, val))
                print(f"  Normalized ESG score: {scores[t]}")
            else:
                print(f"  'totalEsg' not found in sustainability data for {t}")
        except Exception as e:
            print(f"  Error fetching ESG for {t}: {str(e)}")
            continue
    
    print(f"Final ESG scores: {scores}")
    return scores


@app.post("/api/optimize", response_model=OptimizationResult)
async def optimize_portfolio(request: OptimizationRequest):
    """
    Run portfolio optimization with ESG constraints and return all results.
    """
    try:
        # Parse dates - handle both YYYY-MM-DD and ISO datetime formats
        def parse_date(date_str: str) -> dt.date:
            # Remove time component if present (handles ISO format)
            date_only = date_str.split('T')[0]
            return dt.datetime.strptime(date_only, "%Y-%m-%d").date()
        
        start_date = parse_date(request.start_date)
        end_date = parse_date(request.end_date)
        
        # Validate inputs
        if not request.tickers:
            raise HTTPException(status_code=400, detail="At least one ticker is required")
        
        if request.min_allocation * len(request.tickers) > 1:
            raise HTTPException(
                status_code=400,
                detail="Minimum allocation is too high for the number of tickers"
            )
        
        # Build ESG scores dict - fetch from Yahoo if not provided
        if request.esg_scores:
            esg_dict = {item.ticker: item.esg_score for item in request.esg_scores}
        else:
            # Fetch ESG scores from Yahoo Finance
            esg_dict = fetch_esg_scores(request.tickers)
            # Use default of 0.65 for any tickers where fetch failed
            for ticker in request.tickers:
                if ticker not in esg_dict:
                    esg_dict[ticker] = 0.65
        
        # Fetch price data
        try:
            prices = fetch_price_history(request.tickers, start_date, end_date)
            risk_free = fetch_risk_free_rate(start_date, end_date)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Data fetch failed: {str(exc)}")
        
        # Validate ESG scores match tickers
        if not all(ticker in esg_dict for ticker in prices.columns):
            raise HTTPException(
                status_code=400,
                detail="ESG score required for each ticker with price data"
            )
        
        # Get ESG scores in same order as prices columns
        esg_scores = np.array([esg_dict[ticker] for ticker in prices.columns])
        
        # Calculate statistics
        mean_excess, cov_matrix = calc_stats(prices, risk_free)
        
        # Validate and clip target ESG
        esg_min, esg_max = esg_scores.min(), esg_scores.max()
        esg_span = esg_max - esg_min
        if esg_span < 1e-8:
            target_esg = float(esg_min)
        else:
            target_esg = float(np.clip(request.target_esg, esg_min + 1e-3, esg_max - 1e-3))
        
        # Run optimization
        try:
            opt = optimize_esg_frontier(
                mean_excess, cov_matrix, esg_scores, target_esg, 
                min_allocation=request.min_allocation
            )
            tangency = max_sharpe_portfolio(mean_excess, cov_matrix, min_allocation=request.min_allocation)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Optimization failed: {str(exc)}")
        
        # Calculate frontier points
        frontier = list(frontier_points(
            mean_excess, cov_matrix, esg_scores, 
            request.min_allocation, step=request.esg_step
        ))
        
        # Calculate individual asset Sharpes
        indiv_sharpes = asset_sharpes(mean_excess, cov_matrix, prices.columns)
        
        # Calculate rolling Sharpe for portfolio
        returns_full = prices.pct_change().dropna()
        aligned_rf = risk_free.reindex(returns_full.index).ffill()
        aligned_weights = opt.weights.reindex(returns_full.columns).fillna(0.0)
        portfolio_daily = (returns_full * aligned_weights).sum(axis=1)
        portfolio_excess = portfolio_daily.sub(aligned_rf, fill_value=0)
        
        window_days = min(len(portfolio_excess), 252 * 5)
        portfolio_sharpe_series = rolling_sharpe(portfolio_excess, window_days)
        
        # Try to get benchmark rolling Sharpe
        bench_close = fetch_benchmark(["SPY", "^GSPC"], returns_full.index.min(), returns_full.index.max())
        rolling_sharpes_list = []
        
        if not bench_close.empty:
            bench_returns = bench_close.pct_change().dropna()
            bench_returns = bench_returns.reindex(returns_full.index).ffill()
            bench_excess = bench_returns.sub(aligned_rf, fill_value=0)
            bench_sharpe_series = rolling_sharpe(bench_excess, window_days)
            
            # Combine portfolio and benchmark into rolling_sharpes
            # Using portfolio sharpe as primary, but you could structure differently
            for date, sharpe_val in portfolio_sharpe_series.items():
                if not np.isnan(sharpe_val):
                    rolling_sharpes_list.append(
                        SharpeDate(date=date.isoformat(), sharpe=float(sharpe_val))
                    )
        else:
            # Only portfolio sharpes
            for date, sharpe_val in portfolio_sharpe_series.items():
                if not np.isnan(sharpe_val):
                    rolling_sharpes_list.append(
                        SharpeDate(date=date.isoformat(), sharpe=float(sharpe_val))
                    )
        
        # Build holdings
        holdings = []
        for ticker in opt.weights.index:
            holdings.append(
                AssetHolding(
                    ticker=ticker,
                    weight=float(opt.weights[ticker]),
                    sector=None,  # Not implemented yet
                    esg_score=float(esg_dict[ticker]),
                    name=None,  # Not implemented yet
                    sharpe=float(indiv_sharpes[ticker])
                )
            )
        
        # Build frontier
        frontier_list = [
            FrontierPoint(target_esg=float(p.target_esg), sharpe=float(p.sharpe))
            for p in frontier
        ]
        
        # Build response
        result = OptimizationResult(
            last_updated=dt.datetime.now().isoformat(),
            constraints={
                "max_weight_per_asset": 1.0,  # Not explicitly constrained in original, using 1.0
                "risk_aversion": 1.0,  # Not implemented yet - placeholder
                "esg_target": float(target_esg)
            },
            metrics=PortfolioMetrics(
                expected_return=0.0,  # Not implemented yet - placeholder
                volatility=0.0,  # Not implemented yet - placeholder
                sharpe_ratio=float(opt.sharpe),
                max_drawdown=0.0  # Not implemented yet - placeholder
            ),
            holdings=holdings,
            frontier=frontier_list,
            rolling_sharpes=rolling_sharpes_list,
            sharpe=float(opt.sharpe),
            tangency_sharpe=float(tangency.sharpe),
            weights={ticker: float(weight) for ticker, weight in opt.weights.items()},
            assets=list(prices.columns)
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(exc)}")


@app.get("/api/health")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": dt.datetime.now().isoformat(),
        "data_lake_available": LAKE_AVAILABLE,
    }


@app.get("/api/gold/health")
async def gold_health():
    """Check if the data lake (gold layer) is reachable and has data."""
    if not LAKE_AVAILABLE:
        return {"available": False, "reason": "Lake IO not configured (missing src.common.io or env)"}
    try:
        df = _read_gold_df("gold/portfolios/dt=*/*.parquet")
        return {
            "available": True,
            "has_portfolios": not df.empty,
            "partition_count": int(df["dt"].nunique()) if not df.empty and "dt" in df.columns else 0,
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)