# Feature Engineering

Feature engineering transforms raw data into inputs for portfolio optimization.

## Modules

### normalize_esg.py

Normalizes ESG scores for use in optimization constraints.

**Input**: `silver/esg_scores/` (z-scores)
**Output**: `features/esg_normalized/`

**Features created**:
- `esg_percentile`: Rank-based percentile (0-1)
- `esg_normalized`: Min-max normalized score (0-1)

**Usage**:
```bash
python -m src.features.normalize_esg
```

### make_returns_cov.py

Computes asset returns and rolling covariance matrices.

**Input**: `silver/prices/`
**Output**: 
- `features/returns/` (daily returns)
- `features/covariances/` (rolling covariance matrices)

**Configuration**:
- `COV_WINDOW_DAYS`: Rolling window size (default: 20)

**Usage**:
```bash
python -m src.features.make_returns_cov
```

## Data Flow

```
Silver Prices → Returns → Covariances
Silver ESG → Normalized ESG
```

## Schema Contracts

Feature tables must conform to contracts in `src/contracts/`:
- `features_returns.json`
- `features_covariances.json`
- `features_esg.json`
