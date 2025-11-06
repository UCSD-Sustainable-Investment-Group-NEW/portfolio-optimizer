# src/orchestration

Workflow definitions and automation hooks for chaining ingestion, feature, optimization, and backtest jobs.

- `flow.py` wires Prefect tasks into a single end-to-end pipeline that runs ingestion through backtesting.
