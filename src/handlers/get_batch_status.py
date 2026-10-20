"""GET /batches/{batchId} -> pipeline progress for the UI."""
import re

from src.common.db import get_connection
from src.common.http import response

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def handler(event, context):
    batch_id = (event.get("pathParameters") or {}).get("batchId", "")
    if not UUID_RE.match(batch_id):
        return response(400, {"error": "invalid batch id"})

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT status, filename, total_rows, valid_rows, invalid_rows, error_sample, emails_sent,
                      created_at, processed_at, matched_at, notified_at
               FROM upload_batches WHERE batch_id = %s::uuid""",
            (batch_id,),
        )
        row = cur.fetchone()
        if not row:
            return response(404, {"error": "batch not found"})
        cols = [d[0] for d in cur.description]
        batch = dict(zip(cols, row))

        cur.execute("SELECT status, count(*) FROM matches WHERE batch_id = %s::uuid GROUP BY status", (batch_id,))
        batch["matches"] = {s: int(c) for s, c in cur.fetchall()}
    finally:
        conn.close()
    return response(200, batch)
