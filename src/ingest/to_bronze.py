import pandas as pd

from src.common.io import write_dataset


def run() -> None:
    prices = pd.read_csv("data/raw/prices_demo.csv", parse_dates=["date"])
    prices["dt"] = prices["date"].dt.strftime("%Y-%m-%d")
    prices_br = prices.rename(columns=str.lower)
    write_dataset(prices_br, "bronze/prices", partition_cols=("dt",))

    esg = pd.read_csv("data/raw/esg_demo.csv", parse_dates=["date"])
    esg["dt"] = esg["date"].dt.strftime("%Y-%m-%d")
    write_dataset(esg.rename(columns=str.lower), "bronze/esg_scores", ("dt",))


if __name__ == "__main__":
    run()
