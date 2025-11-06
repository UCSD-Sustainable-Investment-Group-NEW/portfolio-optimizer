import pandas as pd

from src.common.schemas import enforce_schema


def prices_to_silver() -> None:
    from src.common.io import read_parquet, write_dataset

    df = read_parquet("bronze/prices/dt=*/part*.parquet")
    if "date" in df.columns:
        df = df.rename(columns={"date": "dt"})
    df = df[["asset_id", "ticker", "adj_close", "adj_open", "volume", "dt"]]
    df = enforce_schema(df, "src/contracts/silver_prices.json")
    write_dataset(df, "silver/prices", ("dt",))


def esg_to_silver() -> None:
    from src.common.io import read_parquet, write_dataset

    df = read_parquet("bronze/esg_scores/dt=*/part*.parquet")
    df = df[["asset_id", "provider", "esg_raw", "dt"]]
    df["esg_z"] = df.groupby("dt")["esg_raw"].transform(
        lambda series: (series - series.mean())
        / (series.std(ddof=0) if series.std(ddof=0) else 1.0)
    )
    df = df[["asset_id", "provider", "esg_raw", "esg_z", "dt"]]
    df = enforce_schema(df, "src/contracts/silver_esg_scores.json")
    write_dataset(df, "silver/esg_scores", ("dt",))


if __name__ == "__main__":
    prices_to_silver()
    esg_to_silver()
