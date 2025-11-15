import json
import os

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
    paths = fs.glob(f"{BUCKET}/{key_or_glob}")
    tables = []
    for path in paths:
        with fs.open(path, "rb") as handle:
            tables.append(pq.read_table(handle).to_pandas())
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


def write_json(obj: dict, key: str) -> None:
    fs = _fs()
    with fs.open(f"{BUCKET}/{key}", "w") as handle:
        handle.write(json.dumps(obj, indent=2))
