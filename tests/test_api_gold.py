"""Tests for the FastAPI gold (data lake) endpoints."""
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# Project root and frontend on path so we can import api
_root = Path(__file__).resolve().parent.parent
_frontend = _root / "frontend"
for p in (str(_root), str(_frontend)):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def sample_gold_portfolios():
    return pd.DataFrame({
        "dt": ["2026-01-26", "2026-01-26", "2026-01-26"],
        "asset_id": ["AAPL", "MSFT", "GOOGL"],
        "weight": [0.2, 0.5, 0.3],
    })


@pytest.fixture
def sample_gold_stats():
    return pd.DataFrame({
        "dt": ["2026-01-26"],
        "expected_return": [0.08],
        "volatility": [0.12],
    })


@pytest.fixture
def sample_gold_performance():
    return pd.DataFrame({
        "dt": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "portfolio_return": [0.001, -0.002, 0.003],
        "cumulative_return": [0.001, -0.001, 0.002],
    })


def test_api_health():
    """GET /api/health returns 200 and indicates lake availability."""
    from api import app
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "data_lake_available" in data


def test_api_gold_portfolios_empty(monkeypatch):
    """GET /api/gold/portfolios returns [] when lake has no data."""
    import api as api_mod
    monkeypatch.setattr(api_mod, "_read_gold_df", lambda _: pd.DataFrame())
    client = TestClient(api_mod.app)
    r = client.get("/api/gold/portfolios")
    assert r.status_code == 200
    assert r.json() == []


def test_api_gold_portfolios_latest(monkeypatch, sample_gold_portfolios):
    """GET /api/gold/portfolios?dt=latest returns latest partition."""
    import api as api_mod
    monkeypatch.setattr(api_mod, "_read_gold_df", lambda _: sample_gold_portfolios.copy())
    client = TestClient(api_mod.app)
    r = client.get("/api/gold/portfolios?dt=latest")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert all("dt" in x and "asset_id" in x and "weight" in x for x in data)
    assert data[0]["dt"] == "2026-01-26"
    assert data[0]["asset_id"] == "AAPL"
    assert data[0]["weight"] == 0.2


def test_api_gold_portfolio_stats_latest(monkeypatch, sample_gold_stats):
    """GET /api/gold/portfolio-stats?dt=latest returns stats."""
    import api as api_mod
    monkeypatch.setattr(api_mod, "_read_gold_df", lambda _: sample_gold_stats.copy())
    client = TestClient(api_mod.app)
    r = client.get("/api/gold/portfolio-stats?dt=latest")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["expected_return"] == 0.08
    assert data[0]["volatility"] == 0.12


def test_api_gold_performance(monkeypatch, sample_gold_performance):
    """GET /api/gold/performance returns performance series."""
    import api as api_mod
    monkeypatch.setattr(api_mod, "_read_gold_df", lambda _: sample_gold_performance.copy())
    client = TestClient(api_mod.app)
    r = client.get("/api/gold/performance")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert all("dt" in x and "portfolio_return" in x and "cumulative_return" in x for x in data)


def test_api_gold_latest(monkeypatch, sample_gold_portfolios, sample_gold_stats, sample_gold_performance):
    """GET /api/gold/latest returns combined gold data."""
    import api as api_mod

    def fake_read(glob_pattern):
        if "portfolios" in glob_pattern:
            return sample_gold_portfolios.copy()
        if "portfolio_stats" in glob_pattern:
            return sample_gold_stats.copy()
        if "performance" in glob_pattern:
            return sample_gold_performance.copy()
        return pd.DataFrame()

    monkeypatch.setattr(api_mod, "_read_gold_df", fake_read)
    client = TestClient(api_mod.app)
    r = client.get("/api/gold/latest")
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "data_lake"
    assert "as_of_dt" in data
    assert len(data["portfolios"]) == 3
    assert len(data["portfolio_stats"]) == 1
    assert len(data["performance"]) == 3


def test_api_gold_health_available(monkeypatch, sample_gold_portfolios):
    """GET /api/gold/health returns available when lake has data."""
    import api as api_mod
    monkeypatch.setattr(api_mod, "LAKE_AVAILABLE", True)
    monkeypatch.setattr(api_mod, "_read_gold_df", lambda _: sample_gold_portfolios.copy())
    client = TestClient(api_mod.app)
    r = client.get("/api/gold/health")
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is True
    assert data["has_portfolios"] is True


def test_api_gold_health_unavailable(monkeypatch):
    """GET /api/gold/health returns available=False when lake IO is not configured."""
    import api as api_mod
    monkeypatch.setattr(api_mod, "LAKE_AVAILABLE", False)
    client = TestClient(api_mod.app)
    r = client.get("/api/gold/health")
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is False
    assert "reason" in data


def test_api_gold_health_no_data(monkeypatch):
    """GET /api/gold/health returns has_portfolios=False when lake is empty."""
    import api as api_mod
    monkeypatch.setattr(api_mod, "LAKE_AVAILABLE", True)
    monkeypatch.setattr(api_mod, "_read_gold_df", lambda _: pd.DataFrame())
    client = TestClient(api_mod.app)
    r = client.get("/api/gold/health")
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is True
    assert data["has_portfolios"] is False


def test_api_gold_health_read_error(monkeypatch):
    """GET /api/gold/health returns available=False when read raises."""
    import api as api_mod
    monkeypatch.setattr(api_mod, "LAKE_AVAILABLE", True)
    monkeypatch.setattr(api_mod, "_read_gold_df", lambda _: (_ for _ in ()).throw(OSError("fake IO error")))
    client = TestClient(api_mod.app)
    r = client.get("/api/gold/health")
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is False
    assert "reason" in data and "fake IO error" in data["reason"]


def test_api_gold_performance_start_end(monkeypatch, sample_gold_performance):
    """GET /api/gold/performance?start=...&end=... filters by date range."""
    import api as api_mod
    monkeypatch.setattr(api_mod, "_read_gold_df", lambda _: sample_gold_performance.copy())
    client = TestClient(api_mod.app)
    r = client.get("/api/gold/performance?start=2024-01-01&end=2024-01-02")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["dt"] == "2024-01-01"
    assert data[1]["dt"] == "2024-01-02"


def test_api_gold_latest_all_empty(monkeypatch):
    """GET /api/gold/latest returns empty lists when lake has no data."""
    import api as api_mod
    monkeypatch.setattr(api_mod, "_read_gold_df", lambda _: pd.DataFrame())
    client = TestClient(api_mod.app)
    r = client.get("/api/gold/latest")
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "data_lake"
    assert data["as_of_dt"] == ""
    assert data["portfolios"] == []
    assert data["portfolio_stats"] == []
    assert data["performance"] == []
