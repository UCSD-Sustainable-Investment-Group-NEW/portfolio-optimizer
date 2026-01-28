# Cloud Deployment Guide

This guide covers deploying the Portfolio Optimizer pipeline to cloud infrastructure.

## Architecture Overview

The pipeline is designed for cloud deployment with:
- **S3-compatible storage** (already configured via `s3fs`)
- **Prefect orchestration** (supports Prefect Cloud)
- **Stateless tasks** (can run on containers/serverless)
- **Partitioned Parquet** (efficient for cloud storage)

## Cloud Infrastructure Options

### Option 1: AWS (Recommended)

#### Compute Options

**1. AWS ECS/Fargate (Container-based)**
- **Best for**: Scheduled/on-demand runs
- **Instance types**: 
  - Small (< 100 assets): `t3.medium` (2 vCPU, 4 GB RAM) - ~$0.04/hr
  - Medium (100-500 assets): `t3.large` (2 vCPU, 8 GB RAM) - ~$0.08/hr
  - Large (500+ assets): `m5.xlarge` (4 vCPU, 16 GB RAM) - ~$0.19/hr
- **Storage**: S3 (already configured)
- **Orchestration**: Prefect Cloud or AWS Step Functions

**2. AWS EC2 (Persistent)**
- **Best for**: Continuous processing, development
- **Instance types**: Same as above
- **Cost**: Pay for 24/7 uptime
- **Setup**: Install Python, run Prefect agent

**3. AWS Lambda (Serverless)**
- **Best for**: Event-driven, small datasets
- **Limitations**: 15 min timeout, 10 GB RAM max
- **Cost**: Pay per invocation (~$0.20 per 1M requests)
- **Note**: May need refactoring for longer runs

**4. AWS Batch**
- **Best for**: Large-scale, parallel processing
- **Instance types**: Auto-scaling based on job queue
- **Cost**: Pay only for compute time

#### Storage: S3 Configuration

```bash
# .env for AWS S3
S3_ENDPOINT=  # Leave empty for AWS S3
LAKE_BUCKET=your-portfolio-lake-bucket
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_REGION=us-east-1
```

**S3 Bucket Setup:**
- Create bucket: `aws s3 mb s3://your-portfolio-lake-bucket`
- Enable versioning (optional): `aws s3api put-bucket-versioning --bucket your-portfolio-lake-bucket --versioning-configuration Status=Enabled`
- Lifecycle policies: Move old partitions to Glacier after 90 days

**Estimated S3 Costs:**
- Standard storage: $0.023/GB/month
- For 100 assets, 252 days: ~10 GB → $0.23/month
- Requests: $0.005 per 1,000 PUT requests

#### Recommended AWS Architecture

```
┌─────────────────┐
│  Prefect Cloud  │  (or self-hosted Prefect server)
│   Orchestrator   │
└────────┬─────────┘
         │ Triggers
         ▼
┌─────────────────┐
│  ECS Task       │  (runs pipeline)
│  - Python 3.12  │
│  - Dependencies │
└────────┬─────────┘
         │ Read/Write
         ▼
┌─────────────────┐
│  S3 Bucket      │
│  (Data Lake)    │
└─────────────────┘
```

### Option 2: Google Cloud Platform (GCP)

#### Compute Options

**1. Cloud Run (Serverless Containers)**
- **Best for**: Event-driven, auto-scaling
- **CPU**: 1-8 vCPU
- **Memory**: 128 MB - 32 GB
- **Timeout**: Up to 60 minutes
- **Cost**: Pay per request + compute time

**2. Compute Engine (VMs)**
- **Best for**: Persistent workloads
- **Instance types**: `n1-standard-2` (2 vCPU, 7.5 GB) - ~$0.10/hr
- **Preemptible**: 80% discount for non-critical jobs

**3. Cloud Functions (Serverless)**
- **Best for**: Small, quick jobs
- **Limitations**: 9 min timeout, 8 GB RAM max

#### Storage: GCS Configuration

```bash
# .env for GCS (using s3fs with GCS endpoint)
S3_ENDPOINT=https://storage.googleapis.com
LAKE_BUCKET=your-portfolio-lake-bucket
AWS_ACCESS_KEY_ID=your-gcs-key  # GCS HMAC key
AWS_SECRET_ACCESS_KEY=your-gcs-secret
AWS_REGION=us-central1
```

**GCS Costs:**
- Standard storage: $0.020/GB/month
- Operations: $0.05 per 10,000 operations

### Option 3: Azure

#### Compute Options

**1. Azure Container Instances (ACI)**
- **Best for**: On-demand container runs
- **Cost**: ~$0.000012/second per vCPU

**2. Azure VMs**
- **Best for**: Persistent workloads
- **Instance types**: `Standard_B2s` (2 vCPU, 4 GB) - ~$0.04/hr

**3. Azure Functions**
- **Best for**: Serverless, event-driven
- **Limitations**: 10 min timeout (consumption plan)

#### Storage: Azure Blob Configuration

```bash
# .env for Azure Blob (using s3fs with Azure endpoint)
S3_ENDPOINT=https://your-storage-account.blob.core.windows.net
LAKE_BUCKET=your-container-name
AWS_ACCESS_KEY_ID=your-storage-account-name
AWS_SECRET_ACCESS_KEY=your-storage-account-key
AWS_REGION=westus
```

## Containerization (Docker)

### Dockerfile Example

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY tests/ ./tests/

# Set Python path
ENV PYTHONPATH=/app

# Default command
CMD ["python", "-m", "src.orchestration.flow"]
```

### Build and Push

```bash
# Build image
docker build -t portfolio-optimizer:latest .

# Tag for registry
docker tag portfolio-optimizer:latest your-registry/portfolio-optimizer:latest

# Push to registry
docker push your-registry/portfolio-optimizer:latest
```

## Prefect Cloud Setup

### 1. Create Prefect Cloud Account
- Sign up at https://app.prefect.cloud
- Create a workspace

### 2. Authenticate

```bash
pip install prefect
prefect cloud login
```

### 3. Update Flow for Prefect Cloud

The existing `src/orchestration/flow.py` works with Prefect Cloud. Just deploy:

```bash
# Set Prefect API URL
export PREFECT_API_URL=https://api.prefect.cloud/api/accounts/[account-id]/workspaces/[workspace-id]

# Run flow (will register with Prefect Cloud)
python -m src.orchestration.flow
```

### 4. Deploy as Work Pool

```python
# In src/orchestration/flow.py, add deployment:
from prefect import deploy

if __name__ == "__main__":
    deploy(
        portfolio_pipeline,
        name="portfolio-optimizer-production",
        work_pool_name="ecs-pool",  # or "ec2-pool", etc.
        parameters={}
    )
```

## Cost Estimates

### AWS Example (100 assets, daily runs)

**Compute (ECS Fargate):**
- Task: `t3.large` (2 vCPU, 8 GB)
- Runtime: ~5 minutes per run
- Daily runs: 30 runs/month
- Cost: 30 × 5 min × $0.08/hr = **$0.20/month**

**Storage (S3):**
- Data: ~10 GB
- Cost: 10 GB × $0.023 = **$0.23/month**

**Prefect Cloud:**
- Free tier: 20,000 task runs/month
- Cost: **$0/month** (within free tier)

**Total: ~$0.50/month** for small-scale

### Medium Scale (500 assets, hourly runs)

**Compute:**
- Task: `m5.xlarge` (4 vCPU, 16 GB)
- Runtime: ~10 minutes per run
- Monthly runs: 720 runs
- Cost: 720 × 10 min × $0.19/hr = **$22.80/month**

**Storage:**
- Data: ~50 GB
- Cost: 50 GB × $0.023 = **$1.15/month**

**Total: ~$24/month**

## Performance Optimization for Cloud

### 1. Parallel Processing

```python
# In src/orchestration/flow.py
from prefect import task
from concurrent.futures import ThreadPoolExecutor

@task
def build_features_parallel():
    with ThreadPoolExecutor(max_workers=2) as executor:
        executor.submit(normalize_esg_run)
        executor.submit(features_returns_cov_run)
```

### 2. Incremental Processing

Process only new dates:

```python
# Add date filtering to reads
def read_latest_partition(root: str, last_processed_dt: str):
    return read_parquet(f"{root}/dt>={last_processed_dt}/*.parquet")
```

### 3. Caching

Use Prefect's caching to skip unchanged steps:

```python
@task(cache_key_fn=lambda: "esg-normalization", cache_expiration=timedelta(hours=1))
def normalize_esg_task():
    return normalize_esg_run()
```

### 4. Optimize Solver

For larger problems, use faster solvers:

```python
# In src/optimize/frontier.py
problem.solve(solver=cp.OSQP, verbose=False)  # Faster than SCS for large problems
```

## Security Best Practices

1. **Secrets Management**
   - Use AWS Secrets Manager / Parameter Store
   - Use Prefect Cloud secrets
   - Never commit `.env` files

2. **IAM Roles**
   - Use IAM roles instead of access keys when possible
   - Least privilege: Only S3 read/write to specific bucket

3. **Network Security**
   - Run in private subnets
   - Use VPC endpoints for S3 access
   - Enable S3 bucket encryption

4. **Container Security**
   - Scan images for vulnerabilities
   - Use minimal base images
   - Run as non-root user

## Monitoring & Observability

### Prefect Cloud
- Built-in dashboard
- Task run history
- Error tracking
- Performance metrics

### CloudWatch (AWS)
- Log aggregation
- Metrics: CPU, memory, duration
- Alarms for failures

### Custom Metrics
```python
from prefect import get_run_logger

@task
def optimize_portfolio():
    logger = get_run_logger()
    start_time = time.time()
    result = optimize_run()
    duration = time.time() - start_time
    logger.info(f"Optimization completed in {duration:.2f}s")
    return result
```

## Scaling Strategies

### Horizontal Scaling
- Run multiple pipeline instances in parallel
- Each processes different date ranges or asset universes
- Use Prefect work pools with multiple workers

### Vertical Scaling
- Increase instance size for larger asset universes
- Monitor CPU/memory usage
- Scale up when optimization takes > 30 seconds

### Auto-scaling
- Use ECS auto-scaling based on queue depth
- Scale workers based on Prefect work pool queue

## Recommended Cloud Setup

### Small Scale (< 100 assets)
- **Compute**: AWS ECS Fargate (t3.medium)
- **Storage**: S3 Standard
- **Orchestration**: Prefect Cloud (free tier)
- **Cost**: ~$1-5/month

### Medium Scale (100-500 assets)
- **Compute**: AWS ECS Fargate (m5.xlarge)
- **Storage**: S3 Standard with lifecycle policies
- **Orchestration**: Prefect Cloud
- **Cost**: ~$20-50/month

### Large Scale (500+ assets)
- **Compute**: AWS Batch or ECS with auto-scaling
- **Storage**: S3 with Intelligent Tiering
- **Orchestration**: Prefect Cloud or self-hosted
- **Cost**: ~$100-500/month (depends on frequency)

## Next Steps

1. **Choose cloud provider** (AWS recommended for S3 integration)
2. **Set up S3 bucket** and configure `.env`
3. **Create Docker image** and push to registry
4. **Set up Prefect Cloud** account
5. **Deploy to ECS/Cloud Run/ACI**
6. **Configure monitoring** and alerts
7. **Test with small dataset** before scaling

## Troubleshooting

### High S3 Costs
- Enable S3 lifecycle policies (move to Glacier)
- Use S3 Intelligent Tiering
- Compress Parquet files (already using snappy)

### Slow Performance
- Increase instance size
- Use faster solver (OSQP instead of SCS)
- Enable parallel processing
- Cache intermediate results

### Timeout Issues
- Increase task timeout in Prefect
- Use larger instances (more CPU/RAM)
- Break pipeline into smaller tasks
