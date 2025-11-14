# MinIO Setup Guide

MinIO is an S3-compatible object storage server used for local development. It provides the same API as AWS S3 without requiring cloud infrastructure.

## What is MinIO?

MinIO is a high-performance object storage service that is:
- **S3-compatible**: Works with existing S3 tools and libraries
- **Local**: Runs in Docker, no cloud account needed
- **Lightweight**: Minimal resource usage
- **Production-ready**: Can be used in production environments

## Architecture

```
┌─────────────────┐
│  Your Pipeline  │
│  (Python code)  │
└────────┬────────┘
         │ s3fs / boto3
         │ S3 API calls
         ▼
┌─────────────────┐
│   MinIO Server  │
│  (Docker)       │
│  Port 9000      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ./lake/        │
│  (Local disk)   │
└─────────────────┘
```

## Quick Start

### 1. Start MinIO

```bash
docker-compose up -d minio
```

### 2. Verify It's Running

```bash
docker-compose ps
```

Look for `Up (healthy)` status.

### 3. Create Bucket

```bash
docker-compose exec minio mc alias set local http://localhost:9000 admin admin12345
docker-compose exec minio mc mb local/lake
```

### 4. Access Console

Open http://localhost:9001 and login with:
- Username: `admin`
- Password: `admin12345`

## Configuration

### Default Credentials

- **Access Key**: `admin`
- **Secret Key**: `admin12345`
- **Endpoint**: `http://localhost:9000`
- **Console**: `http://localhost:9001`

**⚠️ Warning**: These are default credentials for local development only. Never use in production.

### Changing Credentials

Edit `docker-compose.yml`:

```yaml
environment:
  MINIO_ROOT_USER: your-username
  MINIO_ROOT_PASSWORD: your-secure-password
```

Then update `.env`:

```bash
AWS_ACCESS_KEY_ID=your-username
AWS_SECRET_ACCESS_KEY=your-secure-password
```

Restart the container:

```bash
docker-compose down
docker-compose up -d minio
```

## Data Storage

### Local Storage

Data is stored in `./lake/` directory, mounted as `/data` in the container.

```
lake/
├── .minio.sys/     # MinIO system files
└── lake/           # Your bucket data
    ├── bronze/
    ├── silver/
    ├── features/
    └── gold/
```

### Backup

To backup MinIO data:

```bash
# Copy the entire lake directory
cp -r lake/ lake-backup/

# Or use MinIO client
docker-compose exec minio mc mirror local/lake /backup/lake
```

## MinIO Client (mc) Commands

The MinIO client is pre-installed in the container. Useful commands:

```bash
# List buckets
docker-compose exec minio mc ls local/

# List objects in bucket
docker-compose exec minio mc ls local/lake/

# Copy file to bucket
docker-compose exec minio mc cp file.txt local/lake/

# Remove object
docker-compose exec minio mc rm local/lake/file.txt

# Get object
docker-compose exec minio mc cp local/lake/file.txt ./

# Set bucket policy (public read)
docker-compose exec minio mc anonymous set download local/lake
```

## Troubleshooting

### Container Won't Start

**Check Docker:**
```bash
docker ps
```

**Check logs:**
```bash
docker-compose logs minio
```

**Common issues:**
- Docker not running
- Port 9000 or 9001 in use
- Permission issues on `./lake/` directory

### Can't Connect from Python

**Verify environment variables:**
```bash
echo $S3_ENDPOINT
echo $LAKE_BUCKET
```

**Test connection:**
```python
import s3fs
import os

fs = s3fs.S3FileSystem(
    key=os.getenv('AWS_ACCESS_KEY_ID'),
    secret=os.getenv('AWS_SECRET_ACCESS_KEY'),
    client_kwargs={'endpoint_url': os.getenv('S3_ENDPOINT')}
)
print(fs.exists('lake/'))
```

### Bucket Not Found

**Create it:**
```bash
docker-compose exec minio mc mb local/lake
```

**Verify:**
```bash
docker-compose exec minio mc ls local/
```

### Data Not Persisting

**Check volume mount:**
```bash
docker-compose exec minio ls -la /data
```

**Verify local directory:**
```bash
ls -la lake/
```

## Production Considerations

For production, consider:

1. **Use AWS S3**: Set `S3_ENDPOINT` to empty string in `.env`
2. **MinIO Server**: Deploy MinIO server separately with proper security
3. **Credentials**: Use IAM roles or secure credential management
4. **Backup**: Set up automated backups
5. **Monitoring**: Add health checks and alerting
6. **Access Control**: Configure bucket policies and IAM

## Migration from MinIO to AWS S3

1. Update `.env`:
   ```bash
   S3_ENDPOINT=  # Empty for AWS
   LAKE_BUCKET=your-aws-bucket
   AWS_ACCESS_KEY_ID=your-aws-key
   AWS_SECRET_ACCESS_KEY=your-aws-secret
   AWS_REGION=us-east-1
   ```

2. Create bucket in AWS (via console or CLI)

3. Code remains the same - s3fs handles both MinIO and AWS S3 transparently

## Resources

- [MinIO Documentation](https://min.io/docs/)
- [MinIO Client Guide](https://min.io/docs/minio/linux/reference/minio-mc.html)
- [S3FS Documentation](https://s3fs.readthedocs.io/)

