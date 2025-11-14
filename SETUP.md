# Setup Guide

Complete setup instructions for the Portfolio Optimizer project.

## Prerequisites

- **Python 3.8+**: Check with `python3 --version`
- **Docker Desktop**: Required for MinIO (local S3-compatible storage)
- **Git**: For cloning the repository

## Step-by-Step Setup

### 1. Clone and Navigate

```bash
git clone <repository-url>
cd portfolio-optimizer
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up MinIO (Local Data Lake)

MinIO provides S3-compatible storage for local development without AWS.

#### 4.1 Start MinIO Container

```bash
docker-compose up -d minio
```

This starts MinIO in the background. Verify it's running:

```bash
docker-compose ps
```

You should see `portfolio-optimizer-minio-1` with status `Up (healthy)`.

#### 4.2 Create the Lake Bucket

MinIO starts empty. Create the required bucket:

```bash
# Configure MinIO client alias
docker-compose exec minio mc alias set local http://localhost:9000 admin admin12345

# Create the bucket
docker-compose exec minio mc mb local/lake

# Verify bucket exists
docker-compose exec minio mc ls local/
```

You should see `lake/` in the output.

#### 4.3 Access MinIO Console

- **URL**: http://localhost:9001
- **Username**: `admin`
- **Password**: `admin12345`

The console lets you browse buckets and files visually.

### 5. Configure Environment Variables

```bash
cp example.env .env
```

Edit `.env` and ensure these values are set:

```bash
S3_ENDPOINT=http://localhost:9000
LAKE_BUCKET=lake
AWS_ACCESS_KEY_ID=admin
AWS_SECRET_ACCESS_KEY=admin12345
AWS_REGION=us-west-2
```

**Important**: The `.env` file is gitignored. Never commit credentials.

### 6. Verify Setup

#### 6.1 Check MinIO Connection

```bash
# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Test connection (if you have boto3/s3fs installed)
python3 -c "
import os
import s3fs
fs = s3fs.S3FileSystem(
    key=os.getenv('AWS_ACCESS_KEY_ID'),
    secret=os.getenv('AWS_SECRET_ACCESS_KEY'),
    client_kwargs={'endpoint_url': os.getenv('S3_ENDPOINT')}
)
print('✓ MinIO connection successful' if fs.exists('lake/') else '✗ Connection failed')
"
```

#### 6.2 Run a Quick Test

```bash
# Run the ingestion step
python -m src.ingest.to_bronze

# Check if data was written
docker-compose exec minio mc ls local/lake/bronze/
```

You should see partitioned directories like `bronze/prices/dt=2024-01-01/`.

## Common Issues

### Docker Not Running

**Error**: `Cannot connect to the Docker daemon`

**Solution**: Start Docker Desktop application

### Port Already in Use

**Error**: `Bind for 0.0.0.0:9000 failed: port is already allocated`

**Solution**: 
1. Find what's using the port: `lsof -i :9000`
2. Stop the conflicting service, or
3. Change ports in `docker-compose.yml`

### Bucket Creation Fails

**Error**: `Bucket already exists` or `Access Denied`

**Solution**:
```bash
# Check if bucket exists
docker-compose exec minio mc ls local/

# If it exists, you're good. If not, try:
docker-compose exec minio mc mb local/lake --ignore-existing
```

### Permission Denied on lake/ Directory

**Error**: Docker volume mount fails

**Solution**:
```bash
mkdir -p lake
chmod 755 lake
```

### Environment Variables Not Loading

**Error**: Code can't find `S3_ENDPOINT` or credentials

**Solution**:
```bash
# Explicitly export variables
export $(cat .env | grep -v '^#' | xargs)

# Or use a tool like direnv or python-dotenv
```

## Production Setup

For production (AWS S3), update `.env`:

```bash
S3_ENDPOINT=  # Leave empty for AWS
LAKE_BUCKET=your-production-bucket
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_REGION=us-east-1
```

Remove MinIO-specific setup steps. Ensure the bucket exists in your AWS account.

## Verification Checklist

- [ ] Docker Desktop is running
- [ ] MinIO container is up and healthy
- [ ] `lake` bucket exists in MinIO
- [ ] `.env` file is configured correctly
- [ ] Environment variables are loaded
- [ ] Can write test data to MinIO
- [ ] MinIO console is accessible at http://localhost:9001

## Next Steps

Once setup is complete, proceed to:
- [README.md](README.md) - Run the pipeline
- [src/README.md](src/README.md) - Understand the codebase structure

