from __future__ import annotations

import pandas as pd


def _normalize(series: pd.Series) -> pd.Series:
    minimum = series.min()
    maximum = series.max()
    if pd.isna(minimum) or pd.isna(maximum) or minimum == maximum:
        return pd.Series(0.5, index=series.index)
    return (series - minimum) / (maximum - minimum)


def run() -> pd.DataFrame:
    from src.common.io import read_parquet, write_dataset
    from src.common.schemas import enforce_schema

    esg = read_parquet("silver/esg_scores/dt=*/*.parquet")
    if esg.empty:
        return pd.DataFrame(columns=["asset_id", "dt", "provider", "esg_z", "esg_percentile", "esg_normalized"])
    esg = esg.copy()
    esg["esg_percentile"] = esg.groupby("dt")["esg_z"].rank(method="first", pct=True)
    esg["esg_normalized"] = esg.groupby("dt")["esg_z"].transform(_normalize)
    esg = esg[
        [
            "asset_id",
            "dt",
            "provider",
            "esg_z",
            "esg_percentile",
            "esg_normalized",
        ]
    ]
    esg = enforce_schema(esg, "src/contracts/features_esg.json")
    write_dataset(esg, "features/esg_normalized", partition_cols=("dt",))
    return esg


if __name__ == "__main__":
    run()
