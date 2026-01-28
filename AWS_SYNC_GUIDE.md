# AWS S3 Sync Guide - Step by Step

This guide walks you through syncing your portfolio optimizer data lake from local MinIO to AWS S3.

## Prerequisites

1. **AWS Account** - You need an active AWS account
2. **AWS CLI** (optional but recommended) - For easier credential management
3. **Python with boto3** - Already installed in your environment

---

## Step 1: Create AWS Account (if you don't have one)

1. Go to [AWS Console](https://aws.amazon.com/console/)
2. Sign up for an account (free tier available)
3. Complete the registration process

---

## Step 2: Create IAM User for Programmatic Access

You need an IAM user with S3 permissions to access your bucket programmatically.

### 2.1 Navigate to IAM

1. Log into AWS Console
2. Search for "IAM" in the top search bar
3. Click on "IAM" service

### 2.2 Create New User

1. Click **"Users"** in the left sidebar
2. Click **"Create user"** button
3. Enter a username (e.g., `portfolio-optimizer-sync`)
4. Click **"Next"**

### 2.3 Set Permissions

1. Select **"Attach policies directly"**
2. Search for and select: **"AmazonS3FullAccess"** (or create a custom policy with only your bucket)
   - **Note:** For production, use a custom policy with least privilege (see Step 2.5)
3. Click **"Next"**
4. Review and click **"Create user"**

### 2.4 Get Access Keys

1. Click on the newly created user
2. Go to **"Security credentials"** tab
3. Scroll to **"Access keys"** section
4. Click **"Create access key"**
5. Select **"Application running outside AWS"**
6. Click **"Next"**
7. Add a description (optional): "Portfolio Optimizer Data Lake Sync"
8. Click **"Create access key"**
9. **IMPORTANT:** Copy both:
   - **Access Key ID** (starts with `AKIA...`)
   - **Secret Access Key** (long string - only shown once!)
10. Click **"Download .csv"** to save them securely
11. Click **"Done"**

**⚠️ Security Warning:** Never commit these keys to git or share them publicly!

---

## Step 3: Create S3 Bucket

### 3.1 Navigate to S3

1. In AWS Console, search for **"S3"**
2. Click on **"S3"** service

### 3.2 Create Bucket

1. Click **"Create bucket"** button
2. **Bucket name:** Choose a unique name (e.g., `portfolio-optimizer-lake-vaibhav`)
   - Must be globally unique across all AWS accounts
   - Lowercase letters, numbers, and hyphens only
   - Cannot be changed later
3. **AWS Region:** Choose your preferred region (e.g., `us-east-1`, `us-west-2`)
   - Closer to you = lower latency
   - Some regions are cheaper
4. **Object Ownership:** Leave default (ACLs disabled)
5. **Block Public Access:** Keep all settings enabled (recommended)
6. **Bucket Versioning:** Optional (enable for production)
7. **Default encryption:** Enable (recommended)
   - Choose **"AWS managed keys (SSE-S3)"**
8. Click **"Create bucket"**

### 3.3 Note Your Bucket Details

- **Bucket name:** `your-bucket-name`
- **Region:** `us-east-1` (or your chosen region)

---

## Step 4: Set Up Credentials Locally

You have two options:

### Option A: Environment Variables (Recommended for Testing)

```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="your-secret-key-here"
export AWS_DEFAULT_REGION="us-east-1"
```

**To make permanent, add to your `~/.zshrc`:**
```bash
echo 'export AWS_ACCESS_KEY_ID="AKIA..."' >> ~/.zshrc
echo 'export AWS_SECRET_ACCESS_KEY="your-secret-key-here"' >> ~/.zshrc
echo 'export AWS_DEFAULT_REGION="us-east-1"' >> ~/.zshrc
source ~/.zshrc
```

### Option B: AWS Credentials File (More Secure)

1. Create credentials file:
```bash
mkdir -p ~/.aws
nano ~/.aws/credentials
```

2. Add your credentials:
```ini
[default]
aws_access_key_id = AKIA...
aws_secret_access_key = your-secret-key-here
```

3. Create config file:
```bash
nano ~/.aws/config
```

4. Add region:
```ini
[default]
region = us-east-1
```

5. Set permissions:
```bash
chmod 600 ~/.aws/credentials
chmod 600 ~/.aws/config
```

---

## Step 5: Test AWS Connection

Test that your credentials work:

```bash
cd /Users/vaibhavmaloo/portfolio-optimizer
python3 << 'EOF'
import boto3
import os

# Test connection
try:
    s3 = boto3.client('s3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    )
    
    # List buckets
    buckets = s3.list_buckets()
    print("✓ AWS connection successful!")
    print(f"Your buckets: {[b['Name'] for b in buckets['Buckets']]}")
except Exception as e:
    print(f"✗ Error: {e}")
    print("Check your credentials and region")
EOF
```

---

## Step 6: Sync Data Lake to S3

Now sync your data:

```bash
cd /Users/vaibhavmaloo/portfolio-optimizer

# Make sure your AWS credentials are set
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-east-1"

# Sync from local MinIO to AWS S3
python scripts/sync_to_aws.py \
  --bucket your-bucket-name \
  --region us-east-1 \
  --local-dir ./lake/lake
```

**Or if you want to sync directly from MinIO:**

```bash
python scripts/sync_to_aws.py \
  --bucket your-bucket-name \
  --region us-east-1 \
  --source-bucket lake \
  --source-endpoint http://localhost:9000
```

---

## Step 7: Verify Sync

Check that files were uploaded:

```bash
python3 << 'EOF'
import boto3
import os

s3 = boto3.client('s3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
)

bucket = 'your-bucket-name'
objects = s3.list_objects_v2(Bucket=bucket, MaxKeys=10)

if 'Contents' in objects:
    print(f"✓ Found {objects['KeyCount']} objects in bucket")
    print("\nSample files:")
    for obj in objects['Contents'][:5]:
        print(f"  - {obj['Key']} ({obj['Size']} bytes)")
else:
    print("No objects found in bucket")
EOF
```

Or check in AWS Console:
1. Go to S3 service
2. Click on your bucket
3. Browse the folder structure

---

## Step 8: Update Environment for Direct S3 Access (Optional)

Once synced, you can configure your pipeline to use AWS S3 directly instead of MinIO:

1. Update `.env` file:
```bash
# Comment out MinIO settings
# S3_ENDPOINT=http://localhost:9000
# AWS_ACCESS_KEY_ID=admin
# AWS_SECRET_ACCESS_KEY=admin12345

# Add AWS S3 settings
S3_ENDPOINT=  # Leave empty for AWS S3
LAKE_BUCKET=your-bucket-name
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_REGION=us-east-1
```

2. Your pipeline will now read/write directly to AWS S3!

---

## Step 9: Set Up Automated Sync (Optional)

Create a cron job or scheduled task to sync regularly:

```bash
# Add to crontab (runs daily at 2 AM)
crontab -e

# Add this line:
0 2 * * * cd /Users/vaibhavmaloo/portfolio-optimizer && /path/to/python scripts/sync_to_aws.py --bucket your-bucket-name --region us-east-1 --local-dir ./lake/lake >> /tmp/sync.log 2>&1
```

---

## Cost Estimation

**S3 Storage Costs (approximate):**
- Standard storage: $0.023 per GB/month
- Your data lake (~5,144 files): ~50-100 MB = **$0.001-0.002/month**
- PUT requests: $0.005 per 1,000 requests
- GET requests: $0.0004 per 1,000 requests

**Total estimated cost: < $1/month** for small-scale usage

---

## Security Best Practices

### 2.5 Create Custom IAM Policy (Production)

Instead of `AmazonS3FullAccess`, create a custom policy with least privilege:

1. Go to IAM → Policies → Create policy
2. Use JSON editor:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```
3. Name it: `PortfolioOptimizerS3Access`
4. Attach to your IAM user

### Additional Security Tips

1. **Enable MFA** on your AWS account
2. **Rotate access keys** every 90 days
3. **Use IAM roles** instead of access keys when running on EC2
4. **Enable S3 bucket versioning** for data protection
5. **Set up lifecycle policies** to move old data to cheaper storage (Glacier)
6. **Enable CloudTrail** to audit S3 access

---

## Troubleshooting

### Error: "Access Denied"
- Check IAM user has S3 permissions
- Verify bucket name is correct
- Check bucket policy doesn't block access

### Error: "InvalidAccessKeyId"
- Verify access key ID is correct
- Check credentials file format
- Ensure no extra spaces in credentials

### Error: "BucketAlreadyExists"
- S3 bucket names are globally unique
- Choose a different bucket name

### Error: "NoSuchBucket"
- Verify bucket name spelling
- Check you're using the correct region
- Ensure bucket exists in your account

### Slow Upload Speed
- Use AWS region closer to you
- Consider using AWS DataSync for large datasets
- Use multipart uploads for large files

---

## Quick Reference

**Required AWS Resources:**
- ✅ IAM User with Access Keys
- ✅ S3 Bucket
- ✅ Appropriate IAM permissions

**Required Information:**
- Access Key ID
- Secret Access Key
- Bucket Name
- AWS Region

**Sync Command:**
```bash
python scripts/sync_to_aws.py \
  --bucket YOUR-BUCKET-NAME \
  --region us-east-1 \
  --local-dir ./lake/lake
```

---

## Next Steps

1. ✅ Get AWS credentials (Steps 1-2)
2. ✅ Create S3 bucket (Step 3)
3. ✅ Set up credentials locally (Step 4)
4. ✅ Test connection (Step 5)
5. ✅ Sync data (Step 6)
6. ✅ Verify sync (Step 7)
7. ✅ (Optional) Configure pipeline for direct S3 access (Step 8)

Good luck! 🚀
