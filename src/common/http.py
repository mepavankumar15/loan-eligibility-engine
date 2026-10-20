"""Small helpers for API Gateway (Lambda proxy) responses."""
import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


def _default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, (Decimal, UUID)):
        return float(o) if isinstance(o, Decimal) else str(o)
    raise TypeError(f"not serialisable: {type(o)}")


def response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=_default),
    }
