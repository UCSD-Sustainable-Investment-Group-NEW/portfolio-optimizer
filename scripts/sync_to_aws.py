#!/usr/bin/env python3
"""
Sync data lake from local/MinIO to AWS S3.

This script syncs all data from the current data lake (MinIO or local) to AWS S3.
It preserves the directory structure and partitions.

Usage:
    python scripts/sync_to_aws.py --bucket your-aws-bucket --region us-east-1
"""
import argparse
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Try to import s3fs for reading from source
try:
    import s3fs
    S3FS_AVAILABLE = True
except ImportError:
    S3FS_AVAILABLE = False
    print("Warning: s3fs not available. Will only sync local files.")


def sync_to_aws(
    source_bucket: str | None,
    source_endpoint: str | None,
    dest_bucket: str,
    dest_region: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    local_lake_dir: str | None = None,
):
    """
    Sync data from source (MinIO/local) to AWS S3.
    
    Args:
        source_bucket: Source bucket name (if using S3/MinIO)
        source_endpoint: Source endpoint URL (if using MinIO)
        dest_bucket: Destination AWS S3 bucket
        dest_region: AWS region for destination bucket
        aws_access_key_id: AWS access key
        aws_secret_access_key: AWS secret key
        local_lake_dir: Local directory path (if syncing from local filesystem)
    """
    # Create S3 client for destination
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=dest_region,
    )
    
    # Check/create destination bucket
    try:
        s3_client.head_bucket(Bucket=dest_bucket)
        print(f"✓ Destination bucket '{dest_bucket}' exists")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            print(f"Creating destination bucket '{dest_bucket}'...")
            try:
                s3_client.create_bucket(
                    Bucket=dest_bucket,
                    CreateBucketConfiguration={"LocationConstraint": dest_region},
                )
                print(f"✓ Bucket '{dest_bucket}' created")
            except ClientError as create_error:
                if create_error.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
                    print(f"✓ Bucket '{dest_bucket}' already exists (owned by you)")
                else:
                    print(f"✗ Error creating bucket: {create_error}")
                    return False
        else:
            print(f"✗ Error checking bucket: {e}")
            return False
    
    # Get list of files to sync
    files_to_sync = []
    
    if local_lake_dir and Path(local_lake_dir).exists():
        # Sync from local filesystem
        print(f"\nScanning local directory: {local_lake_dir}")
        lake_path = Path(local_lake_dir)
        for file_path in lake_path.rglob("*"):
            if file_path.is_file():
                # Get relative path from lake directory
                rel_path = file_path.relative_to(lake_path)
                files_to_sync.append((file_path, str(rel_path)))
    elif source_bucket and S3FS_AVAILABLE:
        # Sync from S3/MinIO source
        print(f"\nScanning source: {source_endpoint or 'S3'}/{source_bucket}")
        fs = s3fs.S3FileSystem(
            key=os.getenv("AWS_ACCESS_KEY_ID") if not source_endpoint else None,
            secret=os.getenv("AWS_SECRET_ACCESS_KEY") if not source_endpoint else None,
            client_kwargs={"endpoint_url": source_endpoint} if source_endpoint else {},
        )
        
        # List all files in source bucket
        prefix = f"{source_bucket}/"
        for path in fs.find(prefix):
            if fs.isfile(path):
                # Remove bucket prefix
                rel_path = path[len(prefix):]
                files_to_sync.append((path, rel_path))
    else:
        print("✗ No source specified. Use --local-dir or ensure source bucket is configured.")
        return False
    
    if not files_to_sync:
        print("⚠ No files found to sync")
        return True
    
    print(f"\nFound {len(files_to_sync)} files to sync")
    
    # Sync files
    uploaded = 0
    skipped = 0
    errors = 0
    
    for source_path, dest_key in files_to_sync:
        try:
            # Check if file already exists in destination
            try:
                s3_client.head_object(Bucket=dest_bucket, Key=dest_key)
                # File exists, check if we should overwrite
                print(f"  ⏭  Skipping (exists): {dest_key}")
                skipped += 1
                continue
            except ClientError as e:
                if e.response["Error"]["Code"] != "404":
                    raise
            
            # Upload file
            if isinstance(source_path, Path):
                # Local file
                with open(source_path, "rb") as f:
                    s3_client.upload_fileobj(f, dest_bucket, dest_key)
            else:
                # S3 file - read and upload
                if S3FS_AVAILABLE:
                    fs_source = s3fs.S3FileSystem(
                        key=os.getenv("AWS_ACCESS_KEY_ID") if not source_endpoint else None,
                        secret=os.getenv("AWS_SECRET_ACCESS_KEY") if not source_endpoint else None,
                        client_kwargs={"endpoint_url": source_endpoint} if source_endpoint else {},
                    )
                    with fs_source.open(source_path, "rb") as f:
                        s3_client.upload_fileobj(f, dest_bucket, dest_key)
                else:
                    print(f"  ✗ Cannot sync {source_path}: s3fs not available")
                    errors += 1
                    continue
            
            print(f"  ✓ Uploaded: {dest_key}")
            uploaded += 1
            
        except Exception as e:
            print(f"  ✗ Error syncing {dest_key}: {e}")
            errors += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("Sync Summary")
    print("=" * 60)
    print(f"Uploaded: {uploaded}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    print(f"Total: {len(files_to_sync)}")
    
    return errors == 0


def main():
    parser = argparse.ArgumentParser(description="Sync data lake to AWS S3")
    parser.add_argument(
        "--bucket",
        type=str,
        required=True,
        help="AWS S3 bucket name (destination)",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    parser.add_argument(
        "--local-dir",
        type=str,
        default=None,
        help="Local lake directory to sync (default: ./lake)",
    )
    parser.add_argument(
        "--source-bucket",
        type=str,
        default=None,
        help="Source bucket (if syncing from S3/MinIO)",
    )
    parser.add_argument(
        "--source-endpoint",
        type=str,
        default=None,
        help="Source endpoint (for MinIO, e.g., http://localhost:9000)",
    )
    parser.add_argument(
        "--aws-key",
        type=str,
        default=None,
        help="AWS access key ID (default: from AWS_ACCESS_KEY_ID env var)",
    )
    parser.add_argument(
        "--aws-secret",
        type=str,
        default=None,
        help="AWS secret access key (default: from AWS_SECRET_ACCESS_KEY env var)",
    )
    
    args = parser.parse_args()
    
    # Get AWS credentials
    aws_key = args.aws_key or os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = args.aws_secret or os.getenv("AWS_SECRET_ACCESS_KEY")
    
    if not aws_key or not aws_secret:
        print("✗ AWS credentials required. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        print("  Or use --aws-key and --aws-secret arguments")
        sys.exit(1)
    
    # Determine source
    local_dir = args.local_dir or ("./lake" if Path("./lake").exists() else None)
    source_bucket = args.source_bucket or os.getenv("LAKE_BUCKET")
    source_endpoint = args.source_endpoint or os.getenv("S3_ENDPOINT")
    
    # If endpoint is set but it's localhost and Docker isn't running, use local dir
    if source_endpoint and "localhost" in source_endpoint:
        if not local_dir:
            local_dir = "./lake"
    
    success = sync_to_aws(
        source_bucket=source_bucket if source_endpoint else None,
        source_endpoint=source_endpoint if source_endpoint and "localhost" not in source_endpoint else None,
        dest_bucket=args.bucket,
        dest_region=args.region,
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        local_lake_dir=local_dir,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
