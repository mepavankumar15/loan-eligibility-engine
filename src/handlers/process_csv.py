"""S3 ObjectCreated -> stream-parse the CSV -> validate -> bulk upsert into Postgres -> trigger n8n workflow B.

Design notes
- The CSV is streamed line by line (never fully loaded in memory) so file size is bounded by the Lambda timeout only.
- Rows are written in chunks of CHUNK_SIZE with one multi-row INSERT ... ON CONFLICT per chunk (fast, idempotent).
- S3 delivers events at-least-once, so we skip batches that were already processed.
"""
import codecs
import csv
import json
import logging
import os
import time
import urllib.request
import uuid
from urllib.parse import unquote_plus

import boto3
from botocore.config import Config

from src.common.db import get_connection
from src.common.validation import normalize_header, parse_row

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CHUNK_SIZE = 500
MAX_ERROR_SAMPLES = 20
USER_COLS = "(user_id, email, monthly_income, credit_score, employment_status, age, upload_batch_id)"


def handler(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        logger.info("Processing s3://%s/%s", bucket, key)
        process_object(bucket, key)
    return {"ok": True}


def batch_id_from_key(key: str) -> str:
    """Keys look like uploads/<batch-uuid>/<file>.csv; fall back to a deterministic id otherwise."""
    parts = key.split("/")
    if len(parts) >= 3:
        try:
            return str(uuid.UUID(parts[1]))
        except ValueError:
            pass
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def process_object(bucket: str, key: str) -> None:
    batch_id = batch_id_from_key(key)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM upload_batches WHERE batch_id = %s::uuid", (batch_id,))
        existing = cur.fetchone()
        if existing and existing[0] not in ("awaiting_upload", "processing", "failed"):
            logger.info("Batch %s already %s - skipping duplicate event", batch_id, existing[0])
            return
        cur.execute(
            """INSERT INTO upload_batches (batch_id, filename, s3_key, status)
               VALUES (%s::uuid, %s, %s, 'processing')
               ON CONFLICT (batch_id) DO UPDATE SET status = 'processing'""",
            (batch_id, key.split("/")[-1], key),
        )
        conn.commit()

        try:
            total, valid, invalid, samples = ingest(conn, bucket, key, batch_id)
        except Exception:
            conn.rollback()
            cur = conn.cursor()
            cur.execute("UPDATE upload_batches SET status = 'failed' WHERE batch_id = %s::uuid", (batch_id,))
            conn.commit()
            raise

        cur = conn.cursor()
        cur.execute(
            """UPDATE upload_batches
               SET status = 'processed', total_rows = %s, valid_rows = %s, invalid_rows = %s,
                   error_sample = %s::jsonb, processed_at = now()
               WHERE batch_id = %s::uuid""",
            (total, valid, invalid, json.dumps(samples), batch_id),
        )
        conn.commit()
        logger.info("Batch %s: %d rows, %d valid, %d invalid", batch_id, total, valid, invalid)

        if valid > 0:
            ok = notify_n8n(batch_id, valid)
            if not ok:
                cur = conn.cursor()
                cur.execute("UPDATE upload_batches SET status = 'webhook_failed' WHERE batch_id = %s::uuid", (batch_id,))
                conn.commit()
    finally:
        conn.close()


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_INTERNAL") or None,
        config=Config(s3={"addressing_style": "path"}),
    )


def ingest(conn, bucket: str, key: str, batch_id: str):
    """Stream the CSV from S3 and upsert users in chunks. Returns (total, valid, invalid, error_samples)."""
    body = _s3_client().get_object(Bucket=bucket, Key=key)["Body"]
    lines = codecs.getreader("utf-8-sig")(body)  # strips a BOM if the CSV came from Excel
    reader = csv.DictReader(lines)
    reader.fieldnames = [normalize_header(h) for h in (reader.fieldnames or [])]

    total = valid = invalid = 0
    samples, chunk = [], []
    for raw in reader:
        total += 1
        record, error = parse_row(raw)
        if error:
            invalid += 1
            if len(samples) < MAX_ERROR_SAMPLES:
                samples.append({"row": total + 1, "error": error})
            continue
        chunk.append(record)
        if len(chunk) >= CHUNK_SIZE:
            valid += upsert_users(conn, chunk, batch_id)
            chunk = []
    if chunk:
        valid += upsert_users(conn, chunk, batch_id)
    return total, valid, invalid, samples


def upsert_users(conn, rows: list, batch_id: str) -> int:
    """One multi-row INSERT per chunk. Duplicate user_ids inside a chunk are collapsed (last one wins)."""
    unique = {r["user_id"]: r for r in rows}
    params = []
    for r in unique.values():
        params.extend([r["user_id"], r["email"], r["monthly_income"], r["credit_score"],
                       r["employment_status"], r["age"], batch_id])
    placeholders = ",".join(["(%s,%s,%s,%s,%s,%s,%s::uuid)"] * len(unique))
    sql = f"""INSERT INTO users {USER_COLS} VALUES {placeholders}
              ON CONFLICT (user_id) DO UPDATE SET
                email = EXCLUDED.email, monthly_income = EXCLUDED.monthly_income,
                credit_score = EXCLUDED.credit_score, employment_status = EXCLUDED.employment_status,
                age = EXCLUDED.age, upload_batch_id = EXCLUDED.upload_batch_id, updated_at = now()"""
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    return len(unique)


def notify_n8n(batch_id: str, valid_rows: int, attempts: int = 4) -> bool:
    """Trigger workflow B. Retries with exponential backoff because n8n may still be starting."""
    payload = json.dumps({"batch_id": batch_id, "valid_rows": valid_rows}).encode()
    req = urllib.request.Request(
        os.environ["N8N_MATCH_WEBHOOK_URL"],
        data=payload,
        headers={"Content-Type": "application/json", "X-Webhook-Secret": os.environ.get("WEBHOOK_SECRET", "")},
        method="POST",
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info("n8n webhook responded %s", resp.status)
                return True
        except Exception as exc:  # noqa: BLE001 - we want to retry on anything
            logger.warning("n8n webhook attempt %d/%d failed: %s", attempt, attempts, exc)
            time.sleep(2 ** attempt)
    return False
