import pandas as pd

from src.common.schemas import enforce_schema


def test_enforce_schema_adds_missing_columns(tmp_path):
    contract_path = "src/contracts/silver_prices.json"
    df = pd.DataFrame(
        {
            "asset_id": ["A"],
            "ticker": ["AAA"],
            "adj_close": [10.0],
            "dt": ["2024-01-01"],
        }
    )
    enforced = enforce_schema(df, contract_path)

    expected_columns = ["asset_id", "ticker", "adj_close", "adj_open", "volume", "dt"]
    assert list(enforced.columns) == expected_columns
    assert str(enforced["volume"].dtype).lower().startswith("int")
    assert pd.isna(enforced.loc[0, "adj_open"])
