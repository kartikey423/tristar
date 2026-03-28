"""Shared dependency injection helpers for FastAPI routes."""

from __future__ import annotations

from functools import lru_cache

from src.backend.core.config import settings
from src.backend.services.audit_log_service import AuditLogService
from src.backend.services.claude_api import ClaudeApiService
from src.backend.services.claude_context_scoring_service import ClaudeContextScoringService
from src.backend.services.context_scoring_service import ContextScoringService
from src.backend.services.ctc_store_fixtures import CTCStoreFixtures
from src.backend.services.delivery_constraint_service import (
    DeliveryConstraintService,
    RedisDeliveryConstraintService,
)
from src.backend.services.fraud_check_service import FraudCheckService
from src.backend.services.hub_api_client import HubApiClient
from src.backend.services.hub_audit_service import HubAuditService
from src.backend.services.hub_store import HubStore, InMemoryHubStore, RedisHubStore
from src.backend.services.inventory_service import InventoryService
from src.backend.services.mock_member_profile_store import MockMemberProfileStore
from src.backend.services.notification_service import NotificationService
from src.backend.services.purchase_event_handler import PurchaseEventHandler
from src.backend.services.scout_audit_service import ScoutAuditService
from src.backend.services.scout_match_service import ScoutMatchService
from src.backend.services.scout_service_auth import scout_auth


# Singletons — created once per application lifetime
@lru_cache(maxsize=1)
def get_claude_service() -> ClaudeApiService:
    return ClaudeApiService()


@lru_cache(maxsize=1)
def get_fraud_service() -> FraudCheckService:
    return FraudCheckService()


@lru_cache(maxsize=1)
def get_hub_client() -> HubApiClient:
    return HubApiClient()


@lru_cache(maxsize=1)
def get_inventory_service() -> InventoryService:
    return InventoryService()


@lru_cache(maxsize=1)
def get_audit_service() -> AuditLogService:
    return AuditLogService()


@lru_cache(maxsize=1)
def get_context_scoring_service() -> ContextScoringService:
    return ContextScoringService()


@lru_cache(maxsize=1)
def get_delivery_constraint_service() -> DeliveryConstraintService:
    return DeliveryConstraintService()


@lru_cache(maxsize=1)
def get_notification_service() -> NotificationService:
    return NotificationService()


@lru_cache(maxsize=1)
def get_purchase_event_handler() -> PurchaseEventHandler:
    return PurchaseEventHandler()


@lru_cache(maxsize=1)
def get_hub_store() -> HubStore:
    """Return RedisHubStore if HUB_REDIS_ENABLED else InMemoryHubStore."""
    if settings.HUB_REDIS_ENABLED:
        return RedisHubStore(redis_url=settings.REDIS_URL)
    return InMemoryHubStore()


@lru_cache(maxsize=1)
def get_hub_audit_service() -> HubAuditService:
    return HubAuditService(database_url=settings.DATABASE_URL)


# ── Scout match pipeline dependencies ─────────────────────────────────────────

@lru_cache(maxsize=1)
def get_claude_context_scoring_service() -> ClaudeContextScoringService:
    return ClaudeContextScoringService()


@lru_cache(maxsize=1)
def get_scout_constraint_service() -> DeliveryConstraintService | RedisDeliveryConstraintService:
    """Return Redis-backed constraints when REDIS_URL is set and HUB_REDIS_ENABLED; else in-memory."""
    if settings.HUB_REDIS_ENABLED:
        return RedisDeliveryConstraintService(redis_url=settings.REDIS_URL)
    return DeliveryConstraintService()


@lru_cache(maxsize=1)
def get_scout_audit_service() -> ScoutAuditService:
    return ScoutAuditService(database_url=settings.DATABASE_URL)


@lru_cache(maxsize=1)
def get_mock_member_store() -> MockMemberProfileStore:
    return MockMemberProfileStore()


@lru_cache(maxsize=1)
def get_ctc_store_fixtures() -> CTCStoreFixtures:
    return CTCStoreFixtures()


@lru_cache(maxsize=1)
def get_scout_match_service() -> ScoutMatchService:
    return ScoutMatchService(
        hub_client=get_hub_client(),
        scorer=get_claude_context_scoring_service(),
        constraints=get_scout_constraint_service(),
        audit=get_scout_audit_service(),
        member_store=get_mock_member_store(),
        store_fixtures=get_ctc_store_fixtures(),
    )
