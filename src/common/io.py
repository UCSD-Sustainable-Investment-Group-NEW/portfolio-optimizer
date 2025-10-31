import json
import os

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import s3fs

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")
BUCKET = os.getenv("LAKE_BUCKET", "lake")


def _fs() -> s3fs.S3FileSystem:
    kwargs = {"client_kwargs": {"endpoint_url": S3_ENDPOINT}} if S3_ENDPOINT else {}
    return s3fs.S3FileSystem(**kwargs)


def to_parquet(df: pd.DataFrame, key: str) -> None:
    fs = _fs()
    with fs.open(f"{BUCKET}/{key}", "wb") as handle:
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, handle, compression="snappy")


def write_dataset(df: pd.DataFrame, root: str, partition_cols=("dt",)) -> None:
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
