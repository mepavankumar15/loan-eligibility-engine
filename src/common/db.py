"""Postgres connection helper (pg8000 is pure Python, so Lambda packaging needs no native build)."""
import os

import pg8000.dbapi


def get_connection():
    """Open a new connection from env vars. Caller is responsible for commit/close."""
    return pg8000.dbapi.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        timeout=10,
    )
