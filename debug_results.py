
import pandas as pd
import numpy as np
from src.common.io import read_parquet, load_dotenv

load_dotenv()

def debug_data_alignment():
    print("Loading data...")
    portfolios_df = read_parquet("gold/portfolios/dt=*/*.parquet")
    cov_df = read_parquet("features/covariances/dt=*/*.parquet")
    
    latest_dt = portfolios_df["dt"].max()
    print(f"Latest Portfolio Date: {latest_dt}")
    
    # Get weights assets
    weights = portfolios_df[portfolios_df["dt"] == latest_dt]
    weight_assets = weights["asset_id"].unique()
    print(f"Portfolio Assets (Count: {len(weight_assets)}): {weight_assets[:5]}...")
    
    # Get covariance assets for that date
    cov_latest = cov_df[cov_df["dt"] == latest_dt]
    if cov_latest.empty:
        print(f"WARNING: No covariance found for {latest_dt}. Checking max date...")
        cov_latest_dt = cov_df["dt"].max()
        print(f"Latest Covariance Date: {cov_latest_dt}")
        cov_latest = cov_df[cov_df["dt"] == cov_latest_dt]
    
    cov_assets = set(cov_latest["asset_i"].unique()) | set(cov_latest["asset_j"].unique())
    print(f"Covariance Assets (Count: {len(cov_assets)}): {list(cov_assets)[:5]}...")
    
    # Check intersection
    missing = [a for a in weight_assets if a not in cov_assets]
    print(f"Assets in Weights but MISSING in Covariance: {len(missing)}")
    if missing:
        print(f"Example missing: {missing[:5]}")
        
    # Check covariance values
    print("\nCovariance Stats:")
    print(cov_latest["cov"].describe())

if __name__ == "__main__":
    debug_data_alignment()
