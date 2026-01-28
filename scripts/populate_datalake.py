#!/usr/bin/env python3
"""
Populate Data Lake with Sample Data

This script generates realistic sample data for the portfolio optimizer pipeline.
It creates price and ESG data for multiple assets over a date range.

Usage:
    python scripts/populate_datalake.py --assets 50 --days 252 --output-dir data/raw
"""

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def generate_price_data(
    assets: list[str],
    start_date: datetime,
    num_days: int,
    initial_price_range: tuple[float, float] = (50.0, 500.0),
) -> pd.DataFrame:
    """
    Generate realistic price data with random walk and volatility.
    
    Args:
        assets: List of asset IDs (tickers)
        start_date: Starting date for the time series
        num_days: Number of trading days to generate
        initial_price_range: (min, max) for initial prices
        
    Returns:
        DataFrame with columns: date, ticker, asset_id, adj_open, adj_close, volume
    """
    dates = pd.date_range(start=start_date, periods=num_days, freq="B")  # Business days
    
    rows = []
    np.random.seed(42)  # For reproducibility
    
    for asset in assets:
        # Initial price
        initial_price = np.random.uniform(*initial_price_range)
        price = initial_price
        
        # Generate daily prices with random walk
        for date in dates:
            # Random walk with drift and volatility
            daily_return = np.random.normal(0.0005, 0.02)  # ~0.05% daily drift, 2% volatility
            price = price * (1 + daily_return)
            
            # Ensure price stays positive
            price = max(price, 1.0)
            
            # Open price (slightly different from previous close)
            open_price = price * (1 + np.random.normal(0, 0.001))
            
            # Volume (random with some correlation to volatility)
            volume = int(np.random.lognormal(15, 0.5))  # Log-normal for realistic volumes
            
            rows.append({
                "date": date,
                "ticker": asset,
                "asset_id": asset,
                "adj_open": round(open_price, 2),
                "adj_close": round(price, 2),
                "volume": volume,
            })
    
    return pd.DataFrame(rows)


def generate_esg_data(
    assets: list[str],
    start_date: datetime,
    num_days: int,
    provider: str = "demo",
    update_frequency: int = 30,  # Update ESG scores every N days
) -> pd.DataFrame:
    """
    Generate ESG score data with periodic updates.
    
    Args:
        assets: List of asset IDs
        start_date: Starting date
        num_days: Number of days
        provider: ESG data provider name
        update_frequency: How often to update scores (in days)
        
    Returns:
        DataFrame with columns: date, asset_id, provider, esg_raw
    """
    dates = pd.date_range(start=start_date, periods=num_days, freq="B")
    
    rows = []
    np.random.seed(123)  # Different seed for ESG
    
    # Generate base ESG scores for each asset (0-100 scale)
    base_scores = {asset: np.random.uniform(20, 90) for asset in assets}
    
    for date in dates:
        # Update scores periodically (simulating quarterly/annual updates)
        if (date - start_date).days % update_frequency == 0:
            # Slight random walk for ESG scores
            for asset in assets:
                base_scores[asset] += np.random.normal(0, 2)
                base_scores[asset] = np.clip(base_scores[asset], 0, 100)
        
        # Add some daily noise (small variations)
        for asset in assets:
            esg_score = base_scores[asset] + np.random.normal(0, 0.5)
            esg_score = np.clip(esg_score, 0, 100)
            
            rows.append({
                "date": date,
                "asset_id": asset,
                "provider": provider,
                "esg_raw": round(esg_score, 2),
            })
    
    return pd.DataFrame(rows)


def generate_asset_universe(num_assets: int, prefix: str = "ASSET") -> list[str]:
    """Generate a list of asset IDs."""
    return [f"{prefix}{i:03d}" for i in range(1, num_assets + 1)]


def main():
    parser = argparse.ArgumentParser(description="Populate data lake with sample data")
    parser.add_argument(
        "--assets",
        type=int,
        default=20,
        help="Number of assets to generate (default: 20)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=252,
        help="Number of trading days to generate (default: 252, ~1 year)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD). Default: 1 year ago",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/raw",
        help="Output directory for CSV files (default: data/raw)",
    )
    parser.add_argument(
        "--asset-prefix",
        type=str,
        default="ASSET",
        help="Prefix for asset IDs (default: ASSET)",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Also run ingestion to populate bronze layer",
    )
    
    args = parser.parse_args()
    
    # Determine start date
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    else:
        # Default: 1 year ago
        start_date = datetime.now() - timedelta(days=365)
    
    # Generate asset universe
    assets = generate_asset_universe(args.assets, args.asset_prefix)
    print(f"Generating data for {len(assets)} assets from {start_date.date()} for {args.days} days...")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate price data
    print("Generating price data...")
    prices_df = generate_price_data(assets, start_date, args.days)
    prices_path = output_dir / "prices_demo.csv"
    prices_df.to_csv(prices_path, index=False)
    print(f"✓ Wrote {len(prices_df)} price records to {prices_path}")
    
    # Generate ESG data
    print("Generating ESG data...")
    esg_df = generate_esg_data(assets, start_date, args.days)
    esg_path = output_dir / "esg_demo.csv"
    esg_df.to_csv(esg_path, index=False)
    print(f"✓ Wrote {len(esg_df)} ESG records to {esg_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Data Generation Summary")
    print("=" * 60)
    print(f"Assets: {len(assets)}")
    print(f"Date range: {prices_df['date'].min().date()} to {prices_df['date'].max().date()}")
    print(f"Trading days: {prices_df['date'].nunique()}")
    print(f"Price records: {len(prices_df)}")
    print(f"ESG records: {len(esg_df)}")
    print(f"\nFiles created:")
    print(f"  - {prices_path}")
    print(f"  - {esg_path}")
    
    # Optionally ingest to bronze
    if args.ingest:
        print("\n" + "=" * 60)
        print("Ingesting to bronze layer...")
        print("=" * 60)
        
        # Check if environment is set up
        if not os.getenv("S3_ENDPOINT") and not os.getenv("LAKE_BUCKET"):
            print("⚠ Warning: S3/MinIO environment variables not set.")
            print("  Set S3_ENDPOINT, LAKE_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
            print("  Or run: export $(cat .env | grep -v '^#' | xargs)")
            return
        
        try:
            from src.ingest.to_bronze import run as ingest_bronze_run
            ingest_bronze_run()
            print("✓ Successfully ingested data to bronze layer")
        except Exception as e:
            print(f"✗ Error during ingestion: {e}")
            print("  Make sure MinIO is running and environment variables are set")
    else:
        print("\n💡 Tip: Run with --ingest to automatically populate the bronze layer")
        print("   Or manually run: python -m src.ingest.to_bronze")


if __name__ == "__main__":
    main()
