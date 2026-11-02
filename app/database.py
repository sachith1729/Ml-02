from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Open one PostgreSQL connection; commit on success and rollback on error."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn
