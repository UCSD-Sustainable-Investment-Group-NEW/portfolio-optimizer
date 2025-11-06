from __future__ import annotations

import pandas as pd


def _pick_weights(weights: pd.DataFrame, dt: pd.Timestamp) -> pd.DataFrame:
    eligible = weights.loc[weights["dt"] <= dt]
    if eligible.empty:
        return pd.DataFrame(columns=weights.columns)
    latest_dt = eligible["dt"].max()
    return eligible.loc[eligible["dt"] == latest_dt]


def run() -> pd.DataFrame:
    from src.common.io import read_parquet, write_dataset
    from src.common.schemas import enforce_schema

    returns = read_parquet("features/returns/dt=*/part*.parquet")
    weights = read_parquet("gold/portfolios/dt=*/part*.parquet")
    if returns.empty or weights.empty:
        return pd.DataFrame(columns=["dt", "portfolio_return", "cumulative_return"])

    returns = returns.copy()
    weights = weights.copy()
    returns["dt"] = pd.to_datetime(returns["dt"])
    weights["dt"] = pd.to_datetime(weights["dt"])
    returns = returns.sort_values("dt")
    weights = weights.sort_values("dt")

    perf_rows = []
    cumulative = 1.0
    for dt in returns["dt"].drop_duplicates():
        day_returns = returns.loc[returns["dt"] == dt]
        active_weights = _pick_weights(weights, dt)
        if active_weights.empty:
            continue
        merged = day_returns.merge(active_weights, on="asset_id", how="inner")
        if merged.empty:
            continue
        daily_return = float((merged["return_1d"] * merged["weight"]).sum())
        cumulative *= 1.0 + daily_return
        perf_rows.append(
            {
                "dt": dt.strftime("%Y-%m-%d"),
                "portfolio_return": daily_return,
                "cumulative_return": cumulative - 1.0,
            }
        )
    if not perf_rows:
        return pd.DataFrame(columns=["dt", "portfolio_return", "cumulative_return"])
    perf = pd.DataFrame(perf_rows)
    perf = enforce_schema(perf, "src/contracts/gold_performance.json")
    write_dataset(perf, "gold/performance", partition_cols=("dt",))
    return perf


if __name__ == "__main__":
    run()
