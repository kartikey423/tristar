"""Scout audit service — append-only SQL log for every match activation outcome.

Writes ScoutActivationRecord rows to scout_activation_log table (CON-002 / AC-017).
Table created synchronously in __init__ so it exists before first async write.

PII guardrails (AC-017):
  - GPS coordinates (lat/lon) are NEVER written.
  - Only member_id, offer_id, score, outcome, scoring_method, and timestamp.

All log_activation() calls are non-blocking: exceptions caught and logged as
WARNING, never propagated to callers.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

import aiosqlite
from loguru import logger

from src.backend.core.config import settings
from src.backend.models.scout_match import ScoutActivationRecord


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scout_activation_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id      VARCHAR(100) NOT NULL,
    offer_id       VARCHAR(36)  NOT NULL,
    score          REAL         NOT NULL,
    rationale      TEXT         NOT NULL,
    scoring_method VARCHAR(20)  NOT NULL,
    outcome        VARCHAR(30)  NOT NULL,
    timestamp      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_INDEX_MEMBER_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_scout_member_id ON scout_activation_log(member_id)"
)
_CREATE_INDEX_TS_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_scout_timestamp ON scout_activation_log(timestamp)"
)


class ScoutAuditService:
    """Append-only audit log for Scout activation outcomes.

    Uses the same database file as HubAuditService (settings.DATABASE_URL).
    Table is created on __init__ so no migration step needed for dev/SQLite.
    """

    def __init__(self, database_url: str | None = None) -> None:
        # Resolve file path from SQLAlchemy-style URL (sqlite+aiosqlite:///path or sqlite:///path)
        url = database_url or settings.DATABASE_URL
        self._db_path = url.split("///", 1)[-1]
        # Create table synchronously so it exists before any async write.
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.execute(_CREATE_INDEX_MEMBER_SQL)
            conn.execute(_CREATE_INDEX_TS_SQL)
            conn.commit()

    async def log_activation(self, record: ScoutActivationRecord) -> None:
        """Append a Scout activation record. Non-blocking — exceptions are swallowed."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO scout_activation_log
                        (member_id, offer_id, score, rationale, scoring_method, outcome, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.member_id,
                        record.offer_id,
                        record.score,
                        record.rationale,
                        record.scoring_method.value,
                        record.outcome.value,
                        record.timestamp,
                    ),
                )
                await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "scout_audit:log_activation failed — record not persisted",
                extra={
                    "member_id": record.member_id,
                    "offer_id": record.offer_id,
                    "error": str(exc),
                },
            )

    async def get_recent(
        self,
        member_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """Return the N most-recent activation records for a member.

        Used by ContextDashboard (REQ-007 / AC-021). Returns empty list on error.
        """
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """
                    SELECT member_id, offer_id, score, scoring_method, outcome, timestamp
                    FROM scout_activation_log
                    WHERE member_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (member_id, limit),
                )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "scout_audit:get_recent failed",
                extra={"member_id": member_id, "error": str(exc)},
            )
            return []
