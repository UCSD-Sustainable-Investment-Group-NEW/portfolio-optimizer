#!/usr/bin/env python3
"""Setup script to create the MinIO bucket and verify connection."""
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
LAKE_BUCKET = os.getenv("LAKE_BUCKET", "lake")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "admin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "admin12345")


def setup_minio():
    """Create the lake bucket in MinIO if it doesn't exist."""
    try:
        # Create S3 client for MinIO
        s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=os.getenv("AWS_REGION", "us-west-2"),
        )

        # Check if bucket exists
        try:
            s3_client.head_bucket(Bucket=LAKE_BUCKET)
            print(f"✓ Bucket '{LAKE_BUCKET}' already exists")
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                # Bucket doesn't exist, create it
                print(f"Creating bucket '{LAKE_BUCKET}'...")
                s3_client.create_bucket(Bucket=LAKE_BUCKET)
                print(f"✓ Bucket '{LAKE_BUCKET}' created successfully")
                return True
            else:
                print(f"✗ Error checking bucket: {e}")
                return False

    except Exception as e:
        print(f"✗ Failed to connect to MinIO at {S3_ENDPOINT}")
        print(f"  Error: {e}")
        print("\nMake sure:")
        print("  1. MinIO is running: docker-compose up -d")
        print("  2. S3_ENDPOINT in .env points to http://localhost:9000")
        return False


if __name__ == "__main__":
    success = setup_minio()
    sys.exit(0 if success else 1)

