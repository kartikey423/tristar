"""Hub audit service — append-only SQL event log for all Hub state changes.

COMP-003: Writes HubAuditEvent rows to hub_audit_log table.
F-004 FIX: Table created synchronously in __init__ using sqlite3,
          ensuring it exists before the first async log_event() call.
All log_event() calls are non-blocking: exceptions are caught and
logged as WARNING, never propagated to callers.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Literal, Optional

import aiosqlite
from loguru import logger
from pydantic import BaseModel

from src.backend.models.offer_brief import OfferStatus


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS hub_audit_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id       VARCHAR(36)  NOT NULL,
    event          VARCHAR(50)  NOT NULL,
    old_status     VARCHAR(20),
    new_status     VARCHAR(20),
    actor_id       VARCHAR(100) NOT NULL,
    fraud_severity VARCHAR(20),
    timestamp      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_INDEX_OFFER_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_hub_audit_offer_id ON hub_audit_log(offer_id)"
)
_CREATE_INDEX_TS_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_hub_audit_timestamp ON hub_audit_log(timestamp)"
)


class HubAuditEvent(BaseModel):
    offer_id: str
    event: Literal["offer_created", "status_transition", "offer_read", "fraud_blocked"]
    old_status: Optional[OfferStatus] = None
    new_status: Optional[OfferStatus] = None
    actor_id: str
    fraud_severity: Optional[str] = None


class HubAuditService:
    """Append-only SQL audit log for Hub events.

    Thread-safe for concurrent async usage. Write failures are caught and
    logged as WARNING — they never propagate to callers (non-blocking).
    """

    def __init__(self, database_url: str) -> None:
        # Resolve DB file path from SQLAlchemy URL (supports sqlite+aiosqlite:/// prefix)
        self._db_path = database_url.replace("sqlite+aiosqlite:///", "")
        # F-004 FIX: create table synchronously so it exists before first async write
        self._create_table_sync()

    def _create_table_sync(self) -> None:
        """Create hub_audit_log table using stdlib sqlite3.

        Runs once at service instantiation (lru_cache singleton). Safe to call
        multiple times — CREATE TABLE IF NOT EXISTS is idempotent.
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(_CREATE_TABLE_SQL)
                conn.execute(_CREATE_INDEX_OFFER_SQL)
                conn.execute(_CREATE_INDEX_TS_SQL)
                conn.commit()
        except Exception as e:
            logger.warning(f"hub_audit_table_init_failed: {e}")

    async def log_event(self, event: HubAuditEvent) -> None:
        """Write an audit row. Catches all exceptions — logs WARNING, never raises."""
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO hub_audit_log
                        (offer_id, event, old_status, new_status, actor_id, fraud_severity, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.offer_id,
                        event.event,
                        event.old_status.value if event.old_status else None,
                        event.new_status.value if event.new_status else None,
                        event.actor_id,
                        event.fraud_severity,
                        timestamp,
                    ),
                )
                await db.commit()
        except Exception as e:
            logger.warning(
                f"hub_audit_write_failed: {e}",
                extra={"offer_id": event.offer_id, "event": event.event},
            )
