# Connecting to Frontend — Final

This document describes how the **Streamlit ESG dashboard** is connected to the **FastAPI backend** so that the UI can either run the optimizer locally or call the API.

## Overview

- **Backend:** `frontend/api.py` — FastAPI app with `POST /api/optimize` and `GET /api/health`.
- **Frontend:** `frontend/esg_dashboard.py` — Streamlit app that can use the backend when an API base URL is set.
- **Optimizer logic:** `frontend/esg_optimizer.py` — Used by both the API and the dashboard when running locally.

## Backend Endpoints

| Method | Endpoint        | Description |
|--------|-----------------|-------------|
| `POST` | `/api/optimize` | Run ESG portfolio optimization; returns weights, frontier, rolling Sharpes, tangency Sharpe. |
| `GET`  | `/api/health`   | Health check; returns status and timestamp. |

**Request body for `/api/optimize`:**  
`tickers`, `start_date`, `end_date`, `min_allocation`, `esg_step`, `target_esg`, and optionally `esg_scores` (list of `{ticker, esg_score}`).

**Response:**  
`OptimizationResult` — `weights`, `sharpe`, `tangency_sharpe`, `holdings`, `frontier`, `rolling_sharpes`, `assets`, etc.

## Frontend Connection

1. **API base URL (optional)**  
   In the dashboard sidebar, the user can set **“API base URL (optional)”** (e.g. `http://localhost:8000`).

2. **When the URL is set**  
   On **“Run optimizer”**, the dashboard sends a `POST` request to `{API_BASE_URL}/api/optimize` with the current form values and uses the JSON response to drive all charts and tables (weights, frontier, rolling Sharpe, tangency Sharpe, etc.).

3. **When the URL is empty**  
   The dashboard runs the optimizer locally via `esg_optimizer` and behaves as before (no API calls).

4. **Benchmark**  
   When using the API, the dashboard does not compute the benchmark (SPY) locally; it shows portfolio rolling Sharpe from the API and a short note that benchmark comparison is not available.

## How to Run

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

Then open the dashboard, set **API base URL** to `http://localhost:8000`, and click **Run optimizer** to use the backend.

## Summary

- Endpoints are defined in `frontend/api.py`; the dashboard in `frontend/esg_dashboard.py` calls them when an API base URL is provided.
- This gives a single “connecting to frontend final” setup: one backend, one dashboard, with the option to use the API or local optimizer.
