from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

from config.settings import settings


@contextmanager
def get_conn():
    with psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=5) as conn:
        yield conn


def serialize(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def serialize_row(row):
    return {key: serialize(value) for key, value in row.items()}


def fetch_all(query, params=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or {})
            return [serialize_row(row) for row in cur.fetchall()]


def fetch_one(query, params=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or {})
            row = cur.fetchone()
            return serialize_row(row) if row else None
