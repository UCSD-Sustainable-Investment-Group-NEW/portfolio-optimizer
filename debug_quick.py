
import pandas as pd
import numpy as np
import os
from src.common.io import read_parquet, load_dotenv

load_dotenv()

def debug_quick():
    print("Loading ONLY latest portfolios...")
    # Assuming standard structure, let's try to list directories first to find latest date without reading all parquet
    # But s3fs glob is used in read_parquet.
    
    # Just read the portfolios, they are small.
    portfolios_df = read_parquet("gold/portfolios/dt=*/*.parquet")
    if portfolios_df.empty:
        print("No portfolios.")
        return
        
    latest_dt = portfolios_df["dt"].max()
    print(f"Latest Portfolio Date: {latest_dt}")
    
    latest_weights = portfolios_df[portfolios_df["dt"] == latest_dt]
    assets_in_weights = latest_weights["asset_id"].unique()
    print(f"Assets in Weights ({len(assets_in_weights)}): {assets_in_weights[:5]}")
    
    print(f"Loading Covariances for {latest_dt}...")
    # Try specific path
    path = f"features/covariances/dt={latest_dt}/*.parquet"
    try:
        cov_df = read_parquet(path)
    except:
        print(f"Could not read exact path {path}, trying wildcard but filtered")
        cov_df = read_parquet("features/covariances/dt=*/*.parquet")
        cov_df = cov_df[cov_df["dt"] == latest_dt]

    if cov_df.empty:
        print(f"!!! NO COVARIANCE DATA FOR {latest_dt} !!!")
    else:
        print(f"Covariance rows: {len(cov_df)}")
        cov_assets = set(cov_df["asset_i"].unique()) | set(cov_df["asset_j"].unique())
        print(f"Assets in Covariance ({len(cov_assets)}): {list(cov_assets)[:5]}")
        
        missing = [a for a in assets_in_weights if a not in cov_assets]
        print(f"MISSING assets (in weights but not cov): {len(missing)}")
        
        print("\nCovariance Value Stats:")
        print(cov_df["cov"].describe())
        
        # Check diagonal elements specifically
        # cov_df has asset_i, asset_j, cov
        diags = cov_df[cov_df["asset_i"] == cov_df["asset_j"]]
        print("\nDiagonal (Variance) Stats:")
        print(diags["cov"].describe())
        
        # Check if we have zeros on diagonal
        zeros = diags[diags["cov"] == 0]
        print(f"Count of 0 variance assets: {len(zeros)}")

if __name__ == "__main__":
    debug_quick()
