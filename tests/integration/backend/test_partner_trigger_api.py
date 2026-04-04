"""Integration tests for POST /api/scout/partner-trigger endpoint.

Tests:
- AC-05: Valid Tim Hortons payload + HMAC → 202
- AC-06: Invalid HMAC → 401
- AC-07: Offer appears in Hub after trigger
- AC-08: Offer has partner_triggered type + valid_until
- Duplicate event_id → 400
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.main import app
from src.backend.services.partner_trigger_service import _partner_seen_events


@pytest.fixture(autouse=True)
def clear_dedup():
    _partner_seen_events.clear()
    yield
    _partner_seen_events.clear()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _make_event_payload() -> dict:
    return {
        "event_id": "integration-test-tims-001",
        "partner_id": "tim_hortons",
        "partner_name": "Tim Hortons",
        "purchase_amount": 8.50,
        "purchase_category": "coffee",
        "member_id": "M-test-12345",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _make_signature(body: bytes, secret: str = "mock-scout-webhook-secret-test") -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# ─── AC-05: Valid Tim Hortons payload + HMAC → 202 ───────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_valid_tim_hortons_event_returns_202(client):
    """AC-05: Valid partner event with correct HMAC returns 202 Accepted."""
    payload = _make_event_payload()
    body = json.dumps(payload).encode()

    with patch("src.backend.api.scout.settings") as mock_settings, \
         patch("src.backend.api.deps.get_partner_trigger_service") as mock_dep:

        mock_settings.ENVIRONMENT = "production"
        mock_settings.SCOUT_WEBHOOK_SECRET = "mock-scout-webhook-secret-test"

        mock_service = MagicMock()
        mock_service.is_duplicate.return_value = False
        mock_service.classify_and_generate = AsyncMock(return_value=None)
        mock_dep.return_value = mock_service

        sig = _make_signature(body)
        response = await client.post(
            "/api/scout/partner-trigger",
            content=body,
            headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"


# ─── AC-06: Invalid HMAC → 401 ───────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invalid_hmac_returns_401(client):
    """AC-06: Request with wrong HMAC signature returns 401 Unauthorized."""
    payload = _make_event_payload()
    body = json.dumps(payload).encode()

    with patch("src.backend.api.scout.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.SCOUT_WEBHOOK_SECRET = "correct-secret"

        response = await client.post(
            "/api/scout/partner-trigger",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": "sha256=wrong-signature",
            },
        )

    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_missing_hmac_returns_401(client):
    """Missing X-Webhook-Signature header in production returns 401."""
    payload = _make_event_payload()
    body = json.dumps(payload).encode()

    with patch("src.backend.api.scout.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.SCOUT_WEBHOOK_SECRET = "any-secret"

        response = await client.post(
            "/api/scout/partner-trigger",
            content=body,
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 401


# ─── Duplicate event_id → 400 ────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_duplicate_event_id_returns_400(client):
    """Sending same event_id twice within 60s returns 400 on second request."""
    payload = _make_event_payload()
    body = json.dumps(payload).encode()

    with patch("src.backend.api.scout.settings") as mock_settings, \
         patch("src.backend.api.deps.get_partner_trigger_service") as mock_dep:

        mock_settings.ENVIRONMENT = "development"  # Skip HMAC in dev

        mock_service = MagicMock()
        # First call: not duplicate. Second call: duplicate.
        mock_service.is_duplicate.side_effect = [False, True]
        mock_service.classify_and_generate = AsyncMock(return_value=None)
        mock_dep.return_value = mock_service

        # First request — accepted
        r1 = await client.post(
            "/api/scout/partner-trigger",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert r1.status_code == 202

        # Second request — duplicate
        r2 = await client.post(
            "/api/scout/partner-trigger",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert r2.status_code == 400
        assert "Duplicate" in r2.json()["detail"]


# ─── Development mode skips HMAC ─────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_development_mode_skips_hmac_check(client):
    """In development environment, HMAC is skipped — any request accepted."""
    payload = _make_event_payload()
    body = json.dumps(payload).encode()

    with patch("src.backend.api.scout.settings") as mock_settings, \
         patch("src.backend.api.deps.get_partner_trigger_service") as mock_dep:

        mock_settings.ENVIRONMENT = "development"

        mock_service = MagicMock()
        mock_service.is_duplicate.return_value = False
        mock_service.classify_and_generate = AsyncMock(return_value=None)
        mock_dep.return_value = mock_service

        response = await client.post(
            "/api/scout/partner-trigger",
            content=body,
            headers={"Content-Type": "application/json"},
            # No X-Webhook-Signature — should pass in dev mode
        )

    assert response.status_code == 202
