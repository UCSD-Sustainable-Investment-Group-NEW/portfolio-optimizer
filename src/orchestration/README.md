# Orchestration

Workflow definitions and automation hooks for chaining ingestion, feature, optimization, and backtest jobs.

## Overview

The orchestration module uses [Prefect](https://www.prefect.io/) to coordinate the end-to-end pipeline. Each stage is defined as a Prefect task, and the main flow chains them together.

## Pipeline Flow

```
ingest_bronze() 
  → promote_to_silver() 
  → build_features() 
  → optimize_portfolio() 
  → backtest_portfolio()
```

### Tasks

1. **ingest_bronze**: Loads raw CSVs into bronze Parquet format
2. **promote_to_silver**: Cleans and validates data, computes z-scores
3. **build_features**: 
   - Normalizes ESG scores (percentiles, min-max)
   - Computes returns and rolling covariance matrices
4. **optimize_portfolio**: Mean-variance optimization with constraints
5. **backtest_portfolio**: Simulates portfolio performance

## Usage

### Run Full Pipeline

```bash
export $(cat .env | grep -v '^#' | xargs)
python -m src.orchestration.flow
```

### Run with Prefect UI

```bash
# Start Prefect server (optional)
prefect server start

# Run the flow
python -m src.orchestration.flow

# View in UI at http://localhost:4200
```

### Individual Task Execution

Each task can be run independently by importing and calling the underlying functions:

```python
from src.ingest.to_bronze import run as ingest_bronze_run
ingest_bronze_run()
```

## Configuration

Task behavior is controlled by environment variables (see main README.md for full list):

- `COV_WINDOW_DAYS`: Window for covariance calculation
- `EXPECTED_RETURN_LOOKBACK`: Lookback period for expected returns
- `RISK_AVERSION`: Risk aversion parameter
- `WEIGHT_CAP`: Maximum weight per asset

## Error Handling

Prefect automatically handles task retries and logging. Check logs for:

- Task failures
- Data validation errors
- MinIO connection issues
- Schema enforcement failures

## Extending the Pipeline

To add new tasks:

1. Create the task function in the appropriate module
2. Import and wrap it in `@task` decorator
3. Add it to the `portfolio_pipeline()` flow
4. Update this README

Example:

```python
@task(name="New Feature")
def new_feature_task() -> None:
    new_feature_run()

@flow(name="Portfolio Optimizer Pipeline")
def portfolio_pipeline() -> None:
    ingest_bronze()
    promote_to_silver()
    build_features()
    new_feature_task()  # Add here
    optimize_portfolio()
    backtest_portfolio()
```
