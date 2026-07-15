"""S3 object storage — same boto3 code path in dev (MinIO) and prod (AWS).

Dev: set `AWS_ENDPOINT_URL=http://minio:9000` (internal) and
`AWS_PUBLIC_ENDPOINT_URL=http://localhost:9000` (browser-facing presigned
URLs). Prod: leave both unset; standard AWS endpoints + IAM creds apply.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import BinaryIO

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError


def _bucket_name() -> str:
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET is not set")
    return bucket


def _client(*, public: bool = False) -> BaseClient:
    """Build an S3 client. `public=True` uses the browser-reachable endpoint
    for presigned URL generation (localhost:9000 in dev, AWS default in prod).
    """
    endpoint = (
        os.getenv("AWS_PUBLIC_ENDPOINT_URL")
        if public
        else os.getenv("AWS_ENDPOINT_URL")
    )
    if public and not endpoint:
        endpoint = os.getenv("AWS_ENDPOINT_URL")

    kwargs: dict = {
        "service_name": "s3",
        "region_name": os.getenv("AWS_REGION", "us-east-1"),
    }
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client(**kwargs)


@lru_cache(maxsize=1)
def _internal_client() -> BaseClient:
    return _client(public=False)


@lru_cache(maxsize=1)
def _public_client() -> BaseClient:
    return _client(public=True)


def object_key(*, family_id, birth_id, filename: str) -> str:
    return f"f/{family_id}/b/{birth_id}/{filename}"


def ensure_bucket() -> None:
    """Create the bucket if it does not exist. Safe to call on every startup."""
    client = _internal_client()
    bucket = _bucket_name()
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in ("404", "NoSuchBucket", "403"):
            raise
        client.create_bucket(Bucket=bucket)


def put_object(
    *,
    key: str,
    body: bytes | BinaryIO,
    content_type: str | None = None,
) -> None:
    extra: dict = {}
    if content_type:
        extra["ContentType"] = content_type
    _internal_client().put_object(
        Bucket=_bucket_name(),
        Key=key,
        Body=body,
        **extra,
    )


def presigned_get_url(key: str, *, expires_in: int | None = None) -> str:
    ttl = expires_in or int(os.getenv("S3_PRESIGN_TTL_SECONDS", "3600"))
    return _public_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket_name(), "Key": key},
        ExpiresIn=ttl,
    )


def get_object_bytes(key: str) -> bytes:
    response = _internal_client().get_object(Bucket=_bucket_name(), Key=key)
    return response["Body"].read()


def get_object_stream(key: str):
    """Boto3 StreamingBody for large objects — read incrementally, never
    buffer whole videos into RAM (see export.py)."""
    return _internal_client().get_object(Bucket=_bucket_name(), Key=key)["Body"]


def delete_objects(keys: list[str]) -> list[str]:
    """Batch-delete objects; returns the keys that failed. DeleteObjects
    caps at 1000 keys per call, so chunk. Missing keys are not errors
    (S3 delete is idempotent)."""
    if not keys:
        return []
    client = _internal_client()
    bucket = _bucket_name()
    failed: list[str] = []
    for i in range(0, len(keys), 1000):
        response = client.delete_objects(
            Bucket=bucket,
            Delete={
                "Objects": [{"Key": key} for key in keys[i : i + 1000]],
                "Quiet": True,
            },
        )
        failed.extend(err["Key"] for err in response.get("Errors", []))
    return failed
