"""Unified Database Adapter supporting SQLite (local/desktop) and PostgreSQL (Cloud SaaS).

Switch to PostgreSQL by setting DATABASE_URL=postgresql://user:pass@host:5432/panelcraft.
Falls back seamlessly to SQLite when DATABASE_URL is unset.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Optional


DEFAULT_SQLITE_PATH = Path(
    os.getenv("PANELCRAFT_DB_PATH", str(Path(__file__).resolve().parent.parent / "panelcraft.db"))
)


def is_postgres_enabled(db_path: Optional[Path] = None) -> bool:
    if db_path is not None and db_path != DEFAULT_SQLITE_PATH:
        return False
    url = os.getenv("DATABASE_URL", "").strip().lower()
    return url.startswith(("postgres://", "postgresql://"))


class DatabaseSession:
    """Thin dialect-agnostic DB session wrapping sqlite3 or psycopg."""

    def __init__(self, db_path: Path = DEFAULT_SQLITE_PATH) -> None:
        self.dialect = "postgresql" if is_postgres_enabled(db_path) else "sqlite"
        if self.dialect == "postgresql":
            url = os.getenv("DATABASE_URL", "")
            try:
                import psycopg  # type: ignore[import-not-found]
                from psycopg.rows import dict_row  # type: ignore[import-not-found]

                self._conn = psycopg.connect(url, row_factory=dict_row)
            except ImportError:
                import psycopg2  # type: ignore[import-not-found]
                from psycopg2.extras import RealDictCursor  # type: ignore[import-not-found]

                self._conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
        else:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            self._conn = conn

    def _adapt_sql(self, sql: str) -> str:
        if self.dialect == "postgresql":
            return sql.replace("?", "%s")
        return sql

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        adapted = self._adapt_sql(sql)
        cur = self._conn.cursor()
        cur.execute(adapted, params)
        return cur

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cur = self.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Optional[dict[str, Any]]:
        cur = self.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DatabaseSession":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is None:
            self.commit()
        else:
            try:
                self._conn.rollback()
            except Exception:
                pass


def get_db_info() -> dict[str, str]:
    if is_postgres_enabled():
        return {"backend": "PostgreSQL (Cloud SaaS)", "target": os.getenv("DATABASE_URL", "").split("@")[-1]}
    return {"backend": "SQLite (Embedded)", "target": str(DEFAULT_SQLITE_PATH.name)}
