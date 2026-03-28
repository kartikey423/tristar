"""Unit tests for HubAuditService — COMP-003."""

import os
import tempfile
import sqlite3

import pytest

from src.backend.services.hub_audit_service import HubAuditEvent, HubAuditService


@pytest.fixture
def tmp_db(tmp_path):
    """Return a temporary SQLite database URL."""
    db_file = tmp_path / "test_audit.db"
    return f"sqlite+aiosqlite:///{db_file}"


@pytest.fixture
def tmp_db_path(tmp_path):
    """Return a temporary SQLite file path."""
    return str(tmp_path / "test_audit.db")


class TestTableCreation:
    def test_init_creates_table(self, tmp_db):
        """F-004 FIX: __init__ creates hub_audit_log table synchronously."""
        service = HubAuditService(database_url=tmp_db)
        db_path = tmp_db.replace("sqlite+aiosqlite:///", "")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='hub_audit_log'"
            )
            result = cursor.fetchone()
        assert result is not None, "hub_audit_log table should exist after __init__"

    def test_init_creates_indexes(self, tmp_db):
        service = HubAuditService(database_url=tmp_db)
        db_path = tmp_db.replace("sqlite+aiosqlite:///", "")
        with sqlite3.connect(db_path) as conn:
            indexes = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
            }
        assert "idx_hub_audit_offer_id" in indexes
        assert "idx_hub_audit_timestamp" in indexes

    def test_init_idempotent_on_second_call(self, tmp_db):
        """Table creation should be safe to call multiple times."""
        HubAuditService(database_url=tmp_db)
        HubAuditService(database_url=tmp_db)  # Should not raise


class TestLogEvent:
    async def test_log_event_writes_row(self, tmp_db):
        service = HubAuditService(database_url=tmp_db)
        event = HubAuditEvent(
            offer_id="test-offer-123",
            event="offer_created",
            actor_id="user-1",
        )
        await service.log_event(event)

        db_path = tmp_db.replace("sqlite+aiosqlite:///", "")
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("SELECT * FROM hub_audit_log").fetchall()

        assert len(rows) == 1
        assert rows[0][1] == "test-offer-123"  # offer_id column
        assert rows[0][2] == "offer_created"   # event column
        assert rows[0][5] == "user-1"          # actor_id column

    async def test_log_event_status_transition(self, tmp_db):
        from src.backend.models.offer_brief import OfferStatus
        service = HubAuditService(database_url=tmp_db)
        event = HubAuditEvent(
            offer_id="offer-456",
            event="status_transition",
            old_status=OfferStatus.draft,
            new_status=OfferStatus.approved,
            actor_id="system",
        )
        await service.log_event(event)

        db_path = tmp_db.replace("sqlite+aiosqlite:///", "")
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT old_status, new_status FROM hub_audit_log").fetchone()

        assert row[0] == "draft"
        assert row[1] == "approved"

    async def test_log_event_db_error_does_not_raise(self, tmp_db):
        """AC-017: non-blocking — DB failures must be swallowed."""
        service = HubAuditService(database_url=tmp_db)
        # Corrupt the db path so writes fail
        service._db_path = "/nonexistent/path/to/db.sqlite"

        event = HubAuditEvent(
            offer_id="offer-789",
            event="offer_read",
            actor_id="user-2",
        )
        # Should NOT raise even though the DB path is invalid
        await service.log_event(event)

    async def test_log_multiple_events(self, tmp_db):
        service = HubAuditService(database_url=tmp_db)
        for i in range(3):
            await service.log_event(
                HubAuditEvent(
                    offer_id=f"offer-{i}",
                    event="offer_created",
                    actor_id="user-1",
                )
            )

        db_path = tmp_db.replace("sqlite+aiosqlite:///", "")
        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM hub_audit_log").fetchone()[0]

        assert count == 3


class TestHubAuditEvent:
    def test_valid_event_creation(self):
        event = HubAuditEvent(
            offer_id="offer-001",
            event="offer_created",
            actor_id="user-1",
        )
        assert event.offer_id == "offer-001"
        assert event.old_status is None
        assert event.new_status is None

    def test_invalid_event_type_raises(self):
        with pytest.raises(Exception):
            HubAuditEvent(
                offer_id="offer-001",
                event="unknown_event",  # type: ignore[arg-type]
                actor_id="user-1",
            )
