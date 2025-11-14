# Portfolio Optimizer

Modern data & research workspace for iterating on ESG-aware portfolio construction. The repo supports a lakehouse-style workflow with bronze → silver ingestion, feature engineering, optimization, and backtesting.

## Current Capabilities

- **Data Lake Infrastructure**: S3/MinIO integration for local and cloud storage
- **Data Pipeline**: Bronze → Silver → Features → Gold data layers
- **Schema Enforcement**: JSON contract-driven validation (`src/common/schemas.py`)
- **Feature Engineering**: Returns, covariances, and ESG normalization
- **Portfolio Optimization**: Mean-variance optimization with constraints
- **Backtesting**: Historical performance simulation
- **Orchestration**: Prefect-based workflow automation

## Quick Start

### Prerequisites

- Python 3.8+
- Docker and Docker Compose
- Virtual environment (recommended)

### Initial Setup

1. **Clone and install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up MinIO (local data lake):**
   ```bash
   # Start MinIO container
   docker-compose up -d minio
   
   # Create the lake bucket
   docker-compose exec minio mc alias set local http://localhost:9000 admin admin12345
   docker-compose exec minio mc mb local/lake
   ```

3. **Configure environment:**
   ```bash
   cp example.env .env
   # Edit .env and ensure these are set:
   # S3_ENDPOINT=http://localhost:9000
   # LAKE_BUCKET=lake
   # AWS_ACCESS_KEY_ID=admin
   # AWS_SECRET_ACCESS_KEY=admin12345
   ```

4. **Verify MinIO is running:**
   - Console: http://localhost:9001 (admin/admin12345)
   - API: http://localhost:9000
   - Check status: `docker-compose ps`

### Running the Pipeline

**Option 1: Full pipeline (Prefect orchestration)**
```bash
export $(cat .env | grep -v '^#' | xargs)
python -m src.orchestration.flow
```

**Option 2: Individual steps**
```bash
# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Ingest raw CSVs to bronze
python -m src.ingest.to_bronze

# Promote to silver
python -m src.ingest.bronze_to_silver

# Build features
python -m src.features.normalize_esg
python -m src.features.make_returns_cov

# Optimize portfolio
python -m src.optimize.frontier

# Backtest
python -m src.backtest.engine
```

## Project Layout

```
data/
  raw/              # Source CSV files
src/
  common/           # IO utilities, schemas, shared code
  ingest/           # Bronze and silver layer jobs
  features/         # Feature engineering (returns, covariances, ESG)
  optimize/         # Portfolio optimization
  backtest/         # Performance simulation
  orchestration/    # Prefect workflow definitions
  contracts/        # JSON schema definitions
gold/               # Final outputs (portfolios, stats, performance)
lake/               # Local MinIO data storage
```

## Data Flow

```
Raw CSVs → Bronze (Parquet) → Silver (Cleaned) → Features → Optimization → Backtest
```

- **Bronze**: Raw ingested data, partitioned by date
- **Silver**: Cleaned data with basic transformations (z-scores, schema enforcement)
- **Features**: Engineered features (returns, covariances, normalized ESG scores)
- **Gold**: Final outputs (optimized portfolios, statistics, backtest results)

## Configuration

Environment variables (set in `.env`):

- `S3_ENDPOINT`: MinIO/S3 endpoint (default: `http://localhost:9000`)
- `LAKE_BUCKET`: Bucket name (default: `lake`)
- `AWS_ACCESS_KEY_ID`: MinIO access key (default: `admin`)
- `AWS_SECRET_ACCESS_KEY`: MinIO secret key (default: `admin12345`)
- `COV_WINDOW_DAYS`: Covariance calculation window (default: `20`)
- `EXPECTED_RETURN_LOOKBACK`: Return lookback period (default: `20`)
- `RISK_AVERSION`: Risk aversion parameter (default: `5.0`)
- `WEIGHT_CAP`: Maximum weight per asset (default: `0.07`)

## Testing

Run the test suite:
```bash
pytest tests/
```

## Troubleshooting

### MinIO Issues

- **Container won't start**: Check Docker is running (`docker ps`)
- **Port conflicts**: Ensure ports 9000 and 9001 are available
- **Bucket not found**: Create it manually: `docker-compose exec minio mc mb local/lake`
- **Connection errors**: Verify `.env` has correct `S3_ENDPOINT` and credentials

### Pipeline Issues

- **Missing data**: Ensure raw CSVs exist in `data/raw/`
- **Schema errors**: Check contract files in `src/contracts/`
- **Import errors**: Verify virtual environment is activated and dependencies installed

## Development

See per-directory READMEs for module-specific documentation:
- `src/ingest/README.md` - Data ingestion details
- `src/features/README.md` - Feature engineering
- `src/optimize/README.md` - Optimization algorithms
- `src/backtest/README.md` - Backtesting engine
- `src/orchestration/README.md` - Workflow orchestration

## Next Steps

- [ ] Expand test coverage
- [ ] Add data validation checks
- [ ] Implement rebalancing strategies
- [ ] Add ESG constraint options
- [ ] Performance monitoring and alerting
