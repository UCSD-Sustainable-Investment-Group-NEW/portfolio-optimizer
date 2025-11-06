import sys
import types

import pandas as pd


pyarrow_stub = types.ModuleType("pyarrow")


class _Table:
    @staticmethod
    def from_pandas(df, preserve_index=False):
        return df


pyarrow_stub.Table = _Table


parquet_stub = types.ModuleType("pyarrow.parquet")


def _write_table(table, handle, compression="snappy"):
    # No-op for tests; serialization is validated by downstream patches.
    return None


def _write_to_dataset(*args, **kwargs):
    # No-op placeholder for dataset writing in tests.
    return None


def _read_table(handle):
    # Return an empty DataFrame for tests that rely on patched IO.
    return types.SimpleNamespace(to_pandas=lambda: pd.DataFrame())


parquet_stub.write_table = _write_table
parquet_stub.write_to_dataset = _write_to_dataset
parquet_stub.read_table = _read_table

sys.modules.setdefault("pyarrow", pyarrow_stub)
sys.modules.setdefault("pyarrow.parquet", parquet_stub)
