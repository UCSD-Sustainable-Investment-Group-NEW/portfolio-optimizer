#!/usr/bin/env python3
"""Simple test to verify MinIO connection using s3fs (already in requirements)."""
import os
import sys

import s3fs

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
BUCKET = os.getenv("LAKE_BUCKET", "lake")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "admin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "admin12345")


def test_connection():
    """Test MinIO connection and bucket access."""
    try:
        # Create S3 filesystem connection
        fs = s3fs.S3FileSystem(
            key=AWS_ACCESS_KEY_ID,
            secret=AWS_SECRET_ACCESS_KEY,
            client_kwargs={"endpoint_url": S3_ENDPOINT},
        )

        # Test bucket access
        bucket_path = f"{BUCKET}/"
        if fs.exists(bucket_path):
            print(f"✓ Successfully connected to MinIO at {S3_ENDPOINT}")
            print(f"✓ Bucket '{BUCKET}' is accessible")
            
            # List contents (should be empty initially)
            contents = fs.ls(bucket_path)
            print(f"✓ Bucket contains {len(contents)} items")
            return True
        else:
            print(f"✗ Bucket '{BUCKET}' not found")
            return False

    except Exception as e:
        print(f"✗ Failed to connect to MinIO")
        print(f"  Error: {e}")
        print(f"\nCheck:")
        print(f"  1. MinIO is running: docker-compose ps")
        print(f"  2. S3_ENDPOINT={S3_ENDPOINT}")
        print(f"  3. Credentials in .env file")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

