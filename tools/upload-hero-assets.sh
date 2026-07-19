#!/usr/bin/env bash
# Upload landing-page hero assets to S3 under assets/hero-section/.
# The backend serves them via GET /assets/hero-section/{filename} (presigned
# 307 redirect) — see backend/main.py.
#
# Dev (MinIO):  AWS_ENDPOINT_URL=http://localhost:9000 \
#               AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
#               S3_BUCKET=lily-media tools/upload-hero-assets.sh <file...>
# Prod:         run on the box (IAM creds): S3_BUCKET=<bucket> tools/upload-hero-assets.sh <file...>
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 <file> [file...]" >&2
  exit 1
fi

: "${S3_BUCKET:?S3_BUCKET must be set}"

for f in "$@"; do
  aws s3 cp "$f" "s3://$S3_BUCKET/assets/hero-section/$(basename "$f")" \
    ${AWS_ENDPOINT_URL:+--endpoint-url "$AWS_ENDPOINT_URL"}
done
