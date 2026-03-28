"""Shared dependency injection helpers for FastAPI routes."""

from __future__ import annotations

from functools import lru_cache

from src.backend.core.config import settings
from src.backend.services.audit_log_service import AuditLogService
from src.backend.services.claude_api import ClaudeApiService
from src.backend.services.context_scoring_service import ContextScoringService
from src.backend.services.delivery_constraint_service import DeliveryConstraintService
from src.backend.services.fraud_check_service import FraudCheckService
from src.backend.services.hub_api_client import HubApiClient
from src.backend.services.hub_audit_service import HubAuditService
from src.backend.services.hub_store import HubStore, InMemoryHubStore, RedisHubStore
from src.backend.services.inventory_service import InventoryService
from src.backend.services.notification_service import NotificationService
from src.backend.services.purchase_event_handler import PurchaseEventHandler
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
