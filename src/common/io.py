import json
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

import importlib
from functools import lru_cache

import pandas as pd
import s3fs

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")
BUCKET = os.getenv("LAKE_BUCKET", "lake")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")


def _fs() -> s3fs.S3FileSystem:
    kwargs = {}
    if S3_ENDPOINT:
        kwargs["client_kwargs"] = {"endpoint_url": S3_ENDPOINT}
    if AWS_ACCESS_KEY_ID:
        kwargs["key"] = AWS_ACCESS_KEY_ID
    if AWS_SECRET_ACCESS_KEY:
        kwargs["secret"] = AWS_SECRET_ACCESS_KEY
    return s3fs.S3FileSystem(**kwargs)


@lru_cache(maxsize=1)
def _arrow():
    try:
        pa = importlib.import_module("pyarrow")
        pq = importlib.import_module("pyarrow.parquet")
    except ModuleNotFoundError as exc:
        raise RuntimeError("pyarrow is required for parquet IO operations.") from exc
    return pa, pq


def to_parquet(df: pd.DataFrame, key: str) -> None:
    pa, pq = _arrow()
    fs = _fs()
    with fs.open(f"{BUCKET}/{key}", "wb") as handle:
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, handle, compression="snappy")


def write_dataset(df: pd.DataFrame, root: str, partition_cols=("dt",)) -> None:
    pa, pq = _arrow()
    fs = _fs()
    pq.write_to_dataset(
        pa.Table.from_pandas(df, preserve_index=False),
        root_path=f"{BUCKET}/{root}",
        filesystem=fs,
        partition_cols=list(partition_cols),
        existing_data_behavior="overwrite_or_ignore",
        compression="snappy",
    )


def read_parquet(key_or_glob: str) -> pd.DataFrame:
    _, pq = _arrow()
    fs = _fs()
    
    # Read individual files and extract partition columns from paths
    paths = fs.glob(f"{BUCKET}/{key_or_glob}")
    tables = []
    for path in paths:
        with fs.open(path, "rb") as handle:
            df = pq.read_table(handle).to_pandas()
            
            # Extract partition columns from path (e.g., dt=2025-01-01)
            # Path format: bucket/root/dt=2025-01-01/file.parquet
            path_parts = path.replace(f"{BUCKET}/", "").split("/")
            for part in path_parts:
                if "=" in part:
                    # Extract partition column name and value
                    col_name, col_value = part.split("=", 1)
                    # Only add if column doesn't already exist
                    if col_name not in df.columns:
                        # Decode URL encoding and extract just the date part if it contains timestamp
                        col_value = urllib.parse.unquote(col_value)
                        # If it's a datetime string, extract just the date part
                        if " " in col_value or "T" in col_value:
                            col_value = col_value.split()[0].split("T")[0]
                        df[col_name] = col_value
                    else:
                        # If column exists, ensure values match (use partition value if different)
                        existing_value = df[col_name].iloc[0] if len(df) > 0 else None
                        col_value = urllib.parse.unquote(part.split("=", 1)[1])
                        if " " in col_value or "T" in col_value:
                            col_value = col_value.split()[0].split("T")[0]
                        # Update if different (shouldn't happen, but just in case)
                        if existing_value != col_value:
                            df[col_name] = col_value
            
            tables.append(df)
    
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


def write_json(obj: dict, key: str) -> None:
    fs = _fs()
    with fs.open(f"{BUCKET}/{key}", "w") as handle:
        handle.write(json.dumps(obj, indent=2))
