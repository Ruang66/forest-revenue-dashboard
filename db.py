"""Postgres persistence layer for the FE Revenue Dashboard.

Stores the entire dashboard state as a single JSONB document keyed by 'fe_dashboard_v2'.
"""
import os
import json
import psycopg2
from psycopg2.extras import Json

DATABASE_URL = os.environ.get("DATABASE_URL")
STATE_KEY = "fe_dashboard_v2"


def _connect():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    # Railway provides a postgresql:// URL. The internal connection does not use
    # SSL, so let libpq decide (default 'prefer') unless PGSSLMODE is explicitly set.
    sslmode = os.environ.get("PGSSLMODE")
    if sslmode:
        return psycopg2.connect(DATABASE_URL, sslmode=sslmode)
    return psycopg2.connect(DATABASE_URL)


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS dashboard_state (
    key        TEXT PRIMARY KEY,
    data       JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def init_db():
    """Create the state table if it does not exist."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
        conn.commit()


def get_state():
    """Return the stored dashboard dict, or {} if nothing saved yet."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
            cur.execute("SELECT data FROM dashboard_state WHERE key = %s", (STATE_KEY,))
            row = cur.fetchone()
        conn.commit()
    if row and row[0]:
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return {}


def save_state(data: dict):
    """Upsert the full dashboard dict (ensures the table exists first)."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
            cur.execute(
                """
                INSERT INTO dashboard_state (key, data, updated_at)
                VALUES (%s, %s, now())
                ON CONFLICT (key)
                DO UPDATE SET data = EXCLUDED.data, updated_at = now()
                """,
                (STATE_KEY, Json(data)),
            )
        conn.commit()
