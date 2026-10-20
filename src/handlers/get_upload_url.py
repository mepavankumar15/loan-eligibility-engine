"""POST /upload-url -> presigned S3 POST so the browser uploads the CSV directly to S3.

Why: pushing a big CSV through API Gateway + Lambda hits the 10 MB / 29 s limits. With a presigned POST the
file never touches Lambda; S3 emits an ObjectCreated event that triggers `process_csv` (event-driven ingestion).
"""
import json
import os
import re
import uuid

import boto3
from botocore.config import Config

from src.common.db import get_connection
from src.common.http import response

MAX_BYTES = 50 * 1024 * 1024  # enforced by S3 itself through the POST policy


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_PUBLIC") or None,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return response(400, {"error": "invalid JSON body"})

    filename = re.sub(r"[^A-Za-z0-9._-]", "_", body.get("filename") or "users.csv")
    if not filename.lower().endswith(".csv"):
        return response(400, {"error": "only .csv files are accepted"})

    batch_id = str(uuid.uuid4())
    key = f"uploads/{batch_id}/{filename}"

    # Register the batch first so the UI can poll it immediately.
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO upload_batches (batch_id, filename, s3_key, status) VALUES (%s::uuid, %s, %s, 'awaiting_upload')",
            (batch_id, filename, key),
        )
        conn.commit()
    finally:
        conn.close()

    post = _s3_client().generate_presigned_post(
        Bucket=os.environ["UPLOAD_BUCKET"],
        Key=key,
        Conditions=[["content-length-range", 1, MAX_BYTES]],
        ExpiresIn=900,
    )
    return response(200, {"batch_id": batch_id, "key": key, "url": post["url"], "fields": post["fields"]})
