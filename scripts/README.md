# Data Lake Population Scripts

Scripts to populate the data lake with sample or real market data.

## Available Scripts

### 1. `populate_datalake.py` - Generate Synthetic Data

Generates realistic synthetic price and ESG data for testing and development.

**Usage:**
```bash
# Basic usage: 20 assets, 252 days (~1 year)
python scripts/populate_datalake.py

# Custom: 50 assets, 2 years of data
python scripts/populate_datalake.py --assets 50 --days 504

# Generate and automatically ingest to bronze
python scripts/populate_datalake.py --assets 100 --days 252 --ingest

# Custom date range
python scripts/populate_datalake.py --assets 30 --start-date 2023-01-01 --days 252
```

**Options:**
- `--assets N`: Number of assets to generate (default: 20)
- `--days N`: Number of trading days (default: 252)
- `--start-date YYYY-MM-DD`: Start date (default: 1 year ago)
- `--output-dir PATH`: Output directory (default: `data/raw`)
- `--asset-prefix PREFIX`: Prefix for asset IDs (default: `ASSET`)
- `--ingest`: Automatically run ingestion to bronze layer

**Features:**
- Realistic price movements (random walk with volatility)
- Realistic trading volumes (log-normal distribution)
- ESG scores with periodic updates
- Proper date formatting for the pipeline

### 2. `fetch_market_data.py` - Fetch Real Market Data

Fetches real stock prices from Yahoo Finance API.

**Prerequisites:**
```bash
pip install yfinance
```

**Usage:**
```bash
# Fetch data for default tickers (AAPL, MSFT, GOOGL, AMZN, TSLA)
python scripts/fetch_market_data.py

# Custom tickers
python scripts/fetch_market_data.py --tickers AAPL MSFT GOOGL --days 252

# Fetch and ingest
python scripts/fetch_market_data.py --tickers AAPL MSFT --days 252 --ingest

# Custom date range
python scripts/fetch_market_data.py --tickers AAPL --start-date 2023-01-01 --end-date 2024-01-01
```

**Options:**
- `--tickers TICKER ...`: Stock tickers (default: AAPL MSFT GOOGL AMZN TSLA)
- `--days N`: Number of days to fetch (default: 252)
- `--start-date YYYY-MM-DD`: Start date
- `--end-date YYYY-MM-DD`: End date (default: today)
- `--output-dir PATH`: Output directory (default: `data/raw`)
- `--ingest`: Automatically run ingestion to bronze layer

**Note:** ESG data is generated as dummy data. For production, integrate with a real ESG provider API.

## Workflow

### Complete Data Lake Population

1. **Generate or fetch data:**
   ```bash
   # Option A: Synthetic data
   python scripts/populate_datalake.py --assets 50 --days 252 --ingest
   
   # Option B: Real data
   python scripts/fetch_market_data.py --tickers AAPL MSFT GOOGL --days 252 --ingest
   ```

2. **Run full pipeline:**
   ```bash
   export $(cat .env | grep -v '^#' | xargs)
   python -m src.orchestration.flow
   ```

3. **Verify data in MinIO:**
   ```bash
   # List bronze layer
   docker-compose exec minio mc ls local/lake/bronze/
   
   # Or access MinIO console at http://localhost:9001
   ```

## Data Format Requirements

### Prices CSV (`prices_demo.csv`)
```csv
date,ticker,asset_id,adj_open,adj_close,volume
2025-01-01,AAPL,AAPL,150.0,151.0,10000000
2025-01-02,AAPL,AAPL,151.0,152.5,12000000
```

Required columns:
- `date`: Date in YYYY-MM-DD format
- `ticker`: Stock ticker symbol
- `asset_id`: Asset identifier (usually same as ticker)
- `adj_open`: Adjusted opening price
- `adj_close`: Adjusted closing price
- `volume`: Trading volume

### ESG CSV (`esg_demo.csv`)
```csv
date,asset_id,provider,esg_raw
2025-01-01,AAPL,demo,75.5
2025-01-02,AAPL,demo,75.8
```

Required columns:
- `date`: Date in YYYY-MM-DD format
- `asset_id`: Asset identifier
- `provider`: ESG data provider name
- `esg_raw`: ESG score (0-100 scale)

## Troubleshooting

### "No module named 'yfinance'"
```bash
pip install yfinance
```

### "S3/MinIO environment variables not set"
Make sure `.env` is configured:
```bash
export $(cat .env | grep -v '^#' | xargs)
```

### "MinIO connection failed"
Ensure MinIO is running:
```bash
docker-compose up -d minio
docker-compose exec minio mc mb local/lake
```

### Data not appearing in bronze layer
Check that ingestion ran successfully:
```bash
python -m src.ingest.to_bronze
```

## Examples

### Generate Large Dataset for Testing
```bash
# 200 assets, 3 years of data
python scripts/populate_datalake.py \
  --assets 200 \
  --days 756 \
  --start-date 2021-01-01 \
  --asset-prefix STOCK \
  --ingest
```

### Fetch S&P 500 Top 10
```bash
python scripts/fetch_market_data.py \
  --tickers AAPL MSFT GOOGL AMZN NVDA META TSLA BRK.B V JNJ \
  --days 504 \
  --ingest
```

### Incremental Data Updates
```bash
# Fetch only last 30 days
python scripts/fetch_market_data.py \
  --tickers AAPL MSFT \
  --days 30 \
  --ingest
```
