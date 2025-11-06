from __future__ import annotations

from prefect import flow, task

from src.backtest.engine import run as backtest_run
from src.features.make_returns_cov import run as features_returns_cov_run
from src.features.normalize_esg import run as normalize_esg_run
from src.ingest.bronze_to_silver import esg_to_silver, prices_to_silver
from src.ingest.to_bronze import run as ingest_bronze_run
from src.optimize.frontier import run as optimize_run


@task(name="Ingest Raw To Bronze")
def ingest_bronze() -> None:
    ingest_bronze_run()


@task(name="Promote Bronze To Silver")
def promote_to_silver() -> None:
    prices_to_silver()
    esg_to_silver()


@task(name="Build Feature Tables")
def build_features() -> None:
    normalize_esg_run()
    features_returns_cov_run()


@task(name="Optimize Portfolio")
def optimize_portfolio() -> None:
    optimize_run()


@task(name="Backtest Portfolio")
def backtest_portfolio() -> None:
    backtest_run()


@flow(name="Portfolio Optimizer Pipeline")
def portfolio_pipeline() -> None:
    ingest_bronze()
    promote_to_silver()
    build_features()
    optimize_portfolio()
    backtest_portfolio()


if __name__ == "__main__":
    portfolio_pipeline()
