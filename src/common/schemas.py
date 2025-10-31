import json

import pandas as pd

from .io import read_parquet  # noqa: F401 (used by callers downstream)


def enforce_schema(df: pd.DataFrame, contract_path: str) -> pd.DataFrame:
    with open(contract_path, "r", encoding="utf-8") as handle:
        spec = json.load(handle)
    cols = spec["columns"]
    for column in cols:
        if column not in df.columns:
            df[column] = pd.NA
    df = df[list(cols.keys())]
    for column, dtype in cols.items():
        if dtype.startswith("float"):
            df[column] = pd.to_numeric(df[column], errors="coerce")
        elif dtype.startswith("int"):
            df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
        else:
            df[column] = df[column].astype("string")
    return df
