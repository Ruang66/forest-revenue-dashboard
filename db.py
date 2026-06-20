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
    # Railway provides a postg:// or postgresql:// URL; psycopg2 accepts both.
    return psycopg2.connect(DATABASE_URL, sslmode=os.environ.get("PGSSLMODE", "require"))


def init_db():
    """Create the state table if it does not exist."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS dashboard_state (
                    key        TEXT PRIMARY KEY,
                    data       JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        conn.commit()


def get_state():
    """Return the stored dashboard dict, or {} if nothing saved yet."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM dashboard_state WHERE key = %s", (STATE_KEY,))
            row = cur.fetchone()
    if row and row[0]:
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return {}


def save_state(data: dict):
    """Upsert the full dashboard dict."""
    with _connect() as conn:
        with conn.cursor() as cur:
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
