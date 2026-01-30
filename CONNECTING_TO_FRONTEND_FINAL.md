# Connecting to Frontend — Final

This document describes how the **Streamlit ESG dashboard** connects to the **FastAPI backend**, including **Data Lake (gold)** vs **Live optimize**, and how to run **fully tested** before **EC2 deployment**.

## Overview

- **Backend:** `frontend/api.py` — FastAPI app with `POST /api/optimize`, `GET /api/health`, and **gold (data lake)** endpoints.
- **Frontend:** `frontend/esg_dashboard.py` — Streamlit app that can use the backend when an API base URL is set, and choose **Data source**: Data Lake (gold) or Live optimize (yfinance).
- **Optimizer logic:** `frontend/esg_optimizer.py` — Used by the API and the dashboard when running **Live optimize** locally.

## Backend Endpoints

### Optimize (live)

| Method | Endpoint        | Description |
|--------|-----------------|-------------|
| `POST` | `/api/optimize` | Run ESG portfolio optimization; returns weights, frontier, rolling Sharpes, tangency Sharpe. |
| `GET`  | `/api/health`   | Health check; returns status, timestamp, and `data_lake_available`. |

**Request body for `/api/optimize`:**  
`tickers`, `start_date`, `end_date`, `min_allocation`, `esg_step`, `target_esg`, and optionally `esg_scores` (list of `{ticker, esg_score}`).

**Response:**  
`OptimizationResult` — `weights`, `sharpe`, `tangency_sharpe`, `holdings`, `frontier`, `rolling_sharpes`, `assets`, etc.

### Data Lake (gold)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/gold/portfolios` | Portfolio weights from gold layer. Query: `?dt=latest` or `?dt=YYYY-MM-DD`. |
| `GET` | `/api/gold/portfolio-stats` | Expected return, volatility. Query: `?dt=latest` or `?dt=YYYY-MM-DD`. |
| `GET` | `/api/gold/performance` | Backtest performance series. Query: `?start=`, `?end=`, `?dt=`. |
| `GET` | `/api/gold/latest` | Combined latest gold data for the dashboard (portfolios, stats, performance). |
| `GET` | `/api/gold/health` | Data lake availability and whether gold portfolios exist. |

When the data lake is unavailable or not configured, gold endpoints return empty data or `available: false`; the API does not raise.

## Frontend Connection

1. **API base URL (optional)**  
   In the dashboard sidebar, set **"API base URL (optional)"** (e.g. `http://localhost:8000` or your EC2 URL).

2. **Data source**  
   - **Data Lake (gold):** Dashboard calls `GET {API_BASE_URL}/api/gold/latest` and shows portfolio weights, stats, and performance from the data lake. No ESG frontier from gold.
   - **Live optimize (yfinance):** On **"Run optimizer"**, the dashboard sends `POST {API_BASE_URL}/api/optimize` and uses the JSON response for all charts and tables.

3. **When the URL is empty**  
   The dashboard runs the optimizer locally via `esg_optimizer` (no API calls).

4. **Benchmark**  
   When using the API for live optimize, the dashboard does not compute the benchmark (SPY) locally; it shows portfolio rolling Sharpe from the API.

## How to Run Locally

**Terminal 1 — Backend:**
```bash
cd frontend
uvicorn api:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
streamlit run esg_dashboard.py
```

Then open the dashboard, set **API base URL** to `http://localhost:8000`, choose **Data source** (Data Lake or Live optimize), and use **Run optimizer** for live mode.

## Run Tests Before Deploy

From the **project root**:

```bash
python -m pytest tests/test_api_gold.py tests/test_pipeline.py tests/test_schemas.py -v
```

- **test_api_gold.py:** Covers `/api/health`, `/api/gold/portfolios`, `/api/gold/portfolio-stats`, `/api/gold/performance`, `/api/gold/latest`, `/api/gold/health` (empty, latest, start/end, unavailable, read error).
- **test_pipeline.py:** Covers returns/covariances, normalize ESG, frontier, backtest.
- **test_schemas.py:** Covers schema enforcement.

All tests should pass before deploying to EC2.

## EC2 Deployment

1. **Instance**  
   Use an AMI with Python 3.10+ (e.g. Amazon Linux 2 or Ubuntu). Open ports 8000 (API) and 8501 (Streamlit) in the security group, or put the API behind a reverse proxy (e.g. nginx) and only expose 443.

2. **Environment**  
   - For **gold endpoints** to work, the API must have access to the data lake (S3 or MinIO). Set env vars (or `.env`) as in the project (e.g. `LAKE_BUCKET`, `AWS_*` or `S3_ENDPOINT` for MinIO).  
   - If the data lake is not configured, gold endpoints return empty data and `/api/gold/health` returns `available: false`.

3. **Run API** (e.g. with a process manager or systemd):
   ```bash
   cd /path/to/portfolio-optimizer/frontend
   uvicorn api:app --host 0.0.0.0 --port 8000
   ```

4. **Run dashboard** (optional, on same or another instance):
   ```bash
   cd /path/to/portfolio-optimizer/frontend
   streamlit run esg_dashboard.py --server.port 8501 --server.address 0.0.0.0
   ```

5. **Dashboard URL**  
   Set **API base URL** to `http://<EC2-public-IP>:8000` (or `https://your-domain` if behind nginx). Choose **Data Lake (gold)** or **Live optimize (yfinance)** as needed.

6. **Security (production)**  
   - Restrict CORS in `api.py` to your dashboard origin.  
   - Prefer HTTPS (nginx/ALB) and limit exposed ports.

## Summary

- **Endpoints:** `frontend/api.py` defines optimize and gold endpoints; the dashboard in `frontend/esg_dashboard.py` calls them when an API base URL is set.
- **Data source:** Data Lake (gold) uses precomputed gold data; Live optimize uses yfinance and `/api/optimize`.
- **Testing:** Run `pytest tests/test_api_gold.py tests/test_pipeline.py tests/test_schemas.py` from the project root before deploying.
- **EC2:** Run API (and optionally Streamlit), configure data lake env if using gold, and point the dashboard at the API URL.
