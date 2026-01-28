#!/usr/bin/env python3
"""
Fetch Real Market Data from APIs

This script fetches real stock price and ESG data from public APIs.
Requires: pip install yfinance (for prices)

Usage:
    python scripts/fetch_market_data.py --tickers AAPL MSFT GOOGL --days 252
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


def fetch_prices(
    tickers: list[str],
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """
    Fetch stock prices from Yahoo Finance.
    
    Args:
        tickers: List of stock tickers
        start_date: Start date
        end_date: End date
        
    Returns:
        DataFrame with columns: date, ticker, asset_id, adj_open, adj_close, volume
    """
    if not YFINANCE_AVAILABLE:
        raise ImportError(
            "yfinance is required. Install with: pip install yfinance"
        )
    
    print(f"Fetching prices for {len(tickers)} tickers from {start_date.date()} to {end_date.date()}...")
    
    # Fetch data
    data = yf.download(
        tickers,
        start=start_date,
        end=end_date,
        progress=True,
    )
    
    if data.empty:
        raise ValueError("No data returned from yfinance. Check tickers and date range.")
    
    # Convert to long format
    rows = []
    
    # Handle MultiIndex columns (multiple tickers) or regular columns (single ticker)
    if isinstance(data.columns, pd.MultiIndex):
        # Multiple tickers: columns are (Price, Ticker) tuples
        # Level 0: Price metrics (Open, Close, High, Low, Volume)
        # Level 1: Ticker symbols
        for ticker in tickers:
            try:
                # Access data by selecting the ticker at level 1
                # The structure is data[(metric, ticker)]
                ticker_open = data[("Open", ticker)] if ("Open", ticker) in data.columns else None
                ticker_close = data[("Close", ticker)] if ("Close", ticker) in data.columns else None
                ticker_volume = data[("Volume", ticker)] if ("Volume", ticker) in data.columns else None
                
                if ticker_open is None or ticker_close is None or ticker_volume is None:
                    print(f"Warning: Missing data columns for {ticker}")
                    continue
                
                # Combine into a dataframe
                ticker_data = pd.DataFrame({
                    "adj_open": ticker_open,
                    "adj_close": ticker_close,  # Using Close as adj_close (yfinance doesn't always provide Adj Close)
                    "volume": ticker_volume
                })
                ticker_data = ticker_data.dropna()
                
                for date, row in ticker_data.iterrows():
                    rows.append({
                        "date": date,
                        "ticker": ticker,
                        "asset_id": ticker,
                        "adj_open": round(float(row["adj_open"]), 2),
                        "adj_close": round(float(row["adj_close"]), 2),
                        "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
                    })
            except (KeyError, TypeError) as e:
                # Skip if ticker not found in data
                print(f"Warning: No data found for {ticker}: {e}")
                continue
    else:
        # Single ticker: columns are just metric names
        ticker = tickers[0] if isinstance(tickers, list) else tickers
        if "Open" in data.columns and "Close" in data.columns and "Volume" in data.columns:
            ticker_data = data[["Open", "Close", "Volume"]].copy()
            ticker_data.columns = ["adj_open", "adj_close", "volume"]
            ticker_data = ticker_data.dropna()
            
            for date, row in ticker_data.iterrows():
                rows.append({
                    "date": date,
                    "ticker": ticker,
                    "asset_id": ticker,
                    "adj_open": round(float(row["adj_open"]), 2),
                    "adj_close": round(float(row["adj_close"]), 2),
                    "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
                })
        else:
            raise ValueError(f"Missing required columns. Available: {data.columns.tolist()}")
    
    if not rows:
        raise ValueError("No valid price data extracted. Check ticker symbols and date range.")
    
    return pd.DataFrame(rows)


def generate_dummy_esg(
    tickers: list[str],
    start_date: datetime,
    end_date: datetime,
    provider: str = "demo",
) -> pd.DataFrame:
    """
    Generate dummy ESG data (since free ESG APIs are limited).
    In production, you would fetch from a real ESG provider.
    
    Args:
        tickers: List of tickers
        start_date: Start date
        end_date: End date
        provider: Provider name
        
    Returns:
        DataFrame with columns: date, asset_id, provider, esg_raw
    """
    import numpy as np
    
    dates = pd.date_range(start=start_date, end=end_date, freq="B")
    np.random.seed(42)
    
    rows = []
    # Generate base ESG scores (50-80 range for most stocks)
    base_scores = {ticker: np.random.uniform(50, 80) for ticker in tickers}
    
    for date in dates:
        for ticker in tickers:
            # Add small random variation
            score = base_scores[ticker] + np.random.normal(0, 1)
            score = max(0, min(100, score))
            
            rows.append({
                "date": date,
                "asset_id": ticker,
                "provider": provider,
                "esg_raw": round(score, 2),
            })
    
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Fetch real market data from APIs")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
        help="Stock tickers to fetch (default: AAPL MSFT GOOGL AMZN TSLA)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=252,
        help="Number of days to fetch (default: 252, ~1 year)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD). Default: N days ago",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD). Default: today",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/raw",
        help="Output directory for CSV files (default: data/raw)",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Also run ingestion to populate bronze layer",
    )
    
    args = parser.parse_args()
    
    # Determine date range
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        end_date = datetime.now()
    
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    else:
        start_date = end_date - timedelta(days=args.days)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Fetch prices
    try:
        prices_df = fetch_prices(args.tickers, start_date, end_date)
        prices_path = output_dir / "prices_demo.csv"
        prices_df.to_csv(prices_path, index=False)
        print(f"✓ Wrote {len(prices_df)} price records to {prices_path}")
    except Exception as e:
        print(f"✗ Error fetching prices: {e}")
        return
    
    # Generate ESG data (dummy for now)
    print("\nGenerating ESG data (using dummy data - replace with real ESG API)...")
    esg_df = generate_dummy_esg(args.tickers, start_date, end_date)
    esg_path = output_dir / "esg_demo.csv"
    esg_df.to_csv(esg_path, index=False)
    print(f"✓ Wrote {len(esg_df)} ESG records to {esg_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Data Fetch Summary")
    print("=" * 60)
    print(f"Tickers: {', '.join(args.tickers)}")
    print(f"Date range: {prices_df['date'].min().date()} to {prices_df['date'].max().date()}")
    print(f"Trading days: {prices_df['date'].nunique()}")
    print(f"Price records: {len(prices_df)}")
    print(f"ESG records: {len(esg_df)}")
    print(f"\nFiles created:")
    print(f"  - {prices_path}")
    print(f"  - {esg_path}")
    
    # Optionally ingest
    if args.ingest:
        print("\n" + "=" * 60)
        print("Ingesting to bronze layer...")
        print("=" * 60)
        
        if not os.getenv("S3_ENDPOINT") and not os.getenv("LAKE_BUCKET"):
            print("⚠ Warning: S3/MinIO environment variables not set.")
            print("  Set S3_ENDPOINT, LAKE_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
            return
        
        try:
            import os
            from src.ingest.to_bronze import run as ingest_bronze_run
            ingest_bronze_run()
            print("✓ Successfully ingested data to bronze layer")
        except Exception as e:
            print(f"✗ Error during ingestion: {e}")


if __name__ == "__main__":
    import os
    main()
