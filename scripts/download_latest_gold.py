#!/usr/bin/env python3
"""
Download the latest gold data (or features if gold is empty) to local JSON files.
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd

from src.common.io import read_parquet


def download_latest_data():
    """Download the latest data from gold layer, or features if gold is empty."""
    output_dir = Path("data/gold")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Try to read gold data
    print("Checking for gold data...")
    portfolios = read_parquet("gold/portfolios/dt=*/*.parquet")
    stats = read_parquet("gold/portfolio_stats/dt=*/*.parquet")
    performance = read_parquet("gold/performance/dt=*/*.parquet")
    
    if not portfolios.empty:
        print(f"✓ Found {len(portfolios)} portfolio records")
        portfolios_path = output_dir / "portfolios.json"
        portfolios.to_json(portfolios_path, orient="records", indent=2, date_format="iso")
        print(f"  Saved to {portfolios_path}")
    
    if not stats.empty:
        print(f"✓ Found {len(stats)} portfolio stats records")
        stats_path = output_dir / "portfolio_stats.json"
        stats.to_json(stats_path, orient="records", indent=2, date_format="iso")
        print(f"  Saved to {stats_path}")
    
    if not performance.empty:
        print(f"✓ Found {len(performance)} performance records")
        performance_path = output_dir / "performance.json"
        performance.to_json(performance_path, orient="records", indent=2, date_format="iso")
        print(f"  Saved to {performance_path}")
    
    # If gold is empty, download latest features data
    if portfolios.empty and stats.empty and performance.empty:
        print("\n⚠ Gold layer is empty. Downloading latest features data instead...")
        
        # Get latest returns
        returns = read_parquet("features/returns/dt=*/*.parquet")
        if not returns.empty:
            # Get latest date
            returns["dt"] = pd.to_datetime(returns["dt"])
            latest_dt = returns["dt"].max()
            latest_returns = returns[returns["dt"] == latest_dt].copy()
            latest_returns["dt"] = latest_returns["dt"].dt.strftime("%Y-%m-%d")
            
            returns_path = output_dir / f"returns_latest_{latest_dt.strftime('%Y%m%d')}.json"
            latest_returns.to_json(returns_path, orient="records", indent=2, date_format="iso")
            print(f"✓ Latest returns ({latest_dt.strftime('%Y-%m-%d')}): {len(latest_returns)} records")
            print(f"  Saved to {returns_path}")
        
        # Get latest covariances
        covariances = read_parquet("features/covariances/dt=*/*.parquet")
        if not covariances.empty:
            covariances["dt"] = pd.to_datetime(covariances["dt"])
            latest_dt = covariances["dt"].max()
            latest_cov = covariances[covariances["dt"] == latest_dt].copy()
            latest_cov["dt"] = latest_cov["dt"].dt.strftime("%Y-%m-%d")
            
            cov_path = output_dir / f"covariances_latest_{latest_dt.strftime('%Y%m%d')}.json"
            latest_cov.to_json(cov_path, orient="records", indent=2, date_format="iso")
            print(f"✓ Latest covariances ({latest_dt.strftime('%Y-%m-%d')}): {len(latest_cov)} records")
            print(f"  Saved to {cov_path}")
        
        # Get latest ESG normalized
        esg = read_parquet("features/esg_normalized/dt=*/*.parquet")
        if not esg.empty:
            esg["dt"] = pd.to_datetime(esg["dt"])
            latest_dt = esg["dt"].max()
            latest_esg = esg[esg["dt"] == latest_dt].copy()
            latest_esg["dt"] = latest_esg["dt"].dt.strftime("%Y-%m-%d")
            
            esg_path = output_dir / f"esg_normalized_latest_{latest_dt.strftime('%Y%m%d')}.json"
            latest_esg.to_json(esg_path, orient="records", indent=2, date_format="iso")
            print(f"✓ Latest ESG normalized ({latest_dt.strftime('%Y-%m-%d')}): {len(latest_esg)} records")
            print(f"  Saved to {esg_path}")
    
    print(f"\n✓ Data downloaded to {output_dir}/")


if __name__ == "__main__":
    # Load environment variables
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
    
    try:
        download_latest_data()
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
