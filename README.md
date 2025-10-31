# Portfolio Optimizer

Modern data & research workspace for iterating on ESG-aware portfolio construction. The repo is currently scaffolded to support a lakehouse-style workflow with bronze → silver ingestion, feature engineering, optimization, and backtesting.

## Current Capabilities
- S3/MinIO IO helpers (`src/common/io.py`) for reading/writing Parquet datasets and JSON contracts with `pyarrow` + `s3fs`.
- Schema enforcement utility (`src/common/schemas.py`) driven by JSON contracts in `src/contracts/`.
- Bronze ingestion job (`src/ingest/to_bronze.py`) that loads demo CSV fixtures into partitioned Parquet datasets.
- Bronze → silver refinement (`src/ingest/bronze_to_silver.py`) that cleans price and ESG data, computes a simple z-score, and enforces contracts.
- Seed CSVs under `data/raw/` to smoke-test the pipeline end-to-end.
- README stubs across the directory tree so collaborators can see the intended structure even before code lands in each module.

## Project Layout
```
data/
  raw/
src/
  common/
  ingest/
  features/
  optimize/
  backtest/
  orchestration/
  contracts/
gold/
logs/
```
See the per-directory READMEs for details on how each area is intended to evolve.

## Running the Smoke Test
1. Create and activate the virtual environment you prefer, then install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `example.env` to `.env` and adjust values. For local MinIO, confirm the `lake` bucket exists and the credentials have write access.
3. Ingest raw CSVs to bronze Parquet:
   ```bash
   python -m src.ingest.to_bronze
   ```
4. Promote bronze data to the silver layer:
   ```bash
   python -m src.ingest.bronze_to_silver
   ```
5. Browse the generated partitions under your S3/MinIO console (`bronze/` and `silver/`) or the local `lake/` directory if running without remote storage.

## Next Steps
- Flesh out the feature engineering, optimization, and backtesting modules.
- Add Prefect flows in `src/orchestration/flow.py` to coordinate the pipeline.
- Expand the seed data and write tests around schema enforcement and downstream computations.
