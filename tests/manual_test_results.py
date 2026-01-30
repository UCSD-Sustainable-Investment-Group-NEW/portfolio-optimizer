
import pandas as pd
import numpy as np
import pytest
from src.optimize.results import _calculate_max_sharpe, OptimizationResult, PortfolioMetrics, AssetHolding, FrontierPoint, SharpeDate

def test_models():
    # Verify models can be instantiated
    metrics = PortfolioMetrics(expected_return=0.1, volatility=0.2, sharpe_ratio=0.5, max_drawdown=-0.1)
    assert metrics.sharpe_ratio == 0.5
    
    holding = AssetHolding(ticker="AAPL", weight=0.5, esg_score=0.8, sharpe=1.2)
    assert holding.ticker == "AAPL"

def test_max_sharpe_calculation():
    # Synthetic data
    # 2 assets
    mu = np.array([0.10, 0.15]) # 10% and 15% returns
    # Covariance: uncorrelated for simplicity
    sigma = np.array([
        [0.04, 0.00], # 20% vol
        [0.00, 0.09]  # 30% vol
    ])
    
    # Create DataFrames
    assets = ["A", "B"]
    exp_ret_series = pd.Series(mu, index=assets)
    cov_df = pd.DataFrame(sigma, index=assets, columns=assets)
    
    # Test unconstrained (except weight cap 0.07? wait, 0.07 cap is very low, let's relax for test or use 1.0)
    sharpe, weights = _calculate_max_sharpe(exp_ret_series, cov_df, weight_cap=1.0)
    
    # Analytical solution for unconstrained max sharpe with identity cov is proportional to mu.
    # With diagonal sigma, w proportional to Sigma^-1 mu = [0.1/0.04, 0.15/0.09] = [2.5, 1.666]
    # Weights should be normalized.
    assert sharpe > 0
    assert weights is not None
    assert np.isclose(np.sum(weights), 1.0)
    assert weights[0] > weights[1] # A has higher Sharpe (0.1/0.2=0.5) vs B (0.15/0.3=0.5)? Wait.
    # A: 0.1/0.2 = 0.5. B: 0.15/0.3 = 0.5. They have EQUAL Sharpe.
    # So weights should be roughly equal if optimized?
    # Mean-Variance optimizer allocates more to lower vol if returns identical sharpe? 
    # Actually if correlations are 0, we combine them to reduce variance.
    
    # Test with ESG constraint
    esg_scores = pd.Series([0.2, 0.9], index=assets) # B has high ESG
    
    # Force high ESG
    sharpe_esg, weights_esg = _calculate_max_sharpe(exp_ret_series, cov_df, esg_scores=esg_scores, min_esg=0.8, weight_cap=1.0)
    
    assert weights_esg is not None
    # Portfolio ESG = w_A * 0.2 + w_B * 0.9 >= 0.8
    # 0.2 w_A + 0.9 (1-w_A) >= 0.8 => 0.2 w_A + 0.9 - 0.9 w_A >= 0.8 => -0.7 w_A >= -0.1 => w_A <= 1/7 (~0.14)
    port_esg = np.dot(weights_esg, esg_scores.values)
    assert port_esg >= 0.8 - 1e-6

if __name__ == "__main__":
    test_models()
    test_max_sharpe_calculation()
    print("All tests passed!")
