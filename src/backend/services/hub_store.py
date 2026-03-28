"""Hub store abstraction — swappable in-memory (dev) and Redis (prod) backends.

COMP-001: HubStore Protocol with InMemoryHubStore and RedisHubStore implementations.
Controlled by HUB_REDIS_ENABLED setting. All methods are async.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Protocol, runtime_checkable

from loguru import logger

from src.backend.models.offer_brief import OfferBrief, OfferStatus, TriggerType


class RedisUnavailableError(Exception):
    """Raised when Redis is unreachable and HUB_REDIS_ENABLED=true."""


class OfferAlreadyExistsError(Exception):
    """Raised when an offer_id already exists in the store."""


@runtime_checkable
class HubStore(Protocol):
    """Protocol defining the Hub storage interface."""

    async def get(self, offer_id: str) -> Optional[OfferBrief]: ...

    async def save(self, offer: OfferBrief) -> None:
        """Save a new offer. Raises OfferAlreadyExistsError if offer_id already exists."""
        ...

    async def update(self, offer: OfferBrief) -> None:
        """Update an existing offer (replace entirely)."""
        ...

    async def list(
        self,
        status_filter: Optional[OfferStatus] = None,
        trigger_type: Optional[TriggerType] = None,
        since: Optional[datetime] = None,
    ) -> list[OfferBrief]: ...

    async def exists(self, offer_id: str) -> bool: ...

    async def ping(self) -> bool:
        """Returns True if the store is healthy."""
        ...


class InMemoryHubStore:
    """In-memory implementation for development and testing.

    Wraps a plain dict. Thread-safe for single-process async usage.
    """

    def __init__(self) -> None:
        self._store: dict[str, OfferBrief] = {}

    def clear(self) -> None:
        """Clear all offers — used by test fixtures."""
        self._store.clear()

    async def get(self, offer_id: str) -> Optional[OfferBrief]:
        return self._store.get(offer_id)

    async def save(self, offer: OfferBrief) -> None:
        if offer.offer_id in self._store:
            raise OfferAlreadyExistsError(f"Offer {offer.offer_id} already exists in Hub")
        self._store[offer.offer_id] = offer

    async def update(self, offer: OfferBrief) -> None:
        self._store[offer.offer_id] = offer

    async def list(
        self,
        status_filter: Optional[OfferStatus] = None,
        trigger_type: Optional[TriggerType] = None,
        since: Optional[datetime] = None,
    ) -> list[OfferBrief]:
        offers = list(self._store.values())

        if status_filter:
            offers = [o for o in offers if o.status == status_filter]

        if trigger_type:
            offers = [o for o in offers if o.trigger_type == trigger_type]

        if since:
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
            offers = [o for o in offers if o.created_at >= since]

        return offers

    async def exists(self, offer_id: str) -> bool:
        return offer_id in self._store

    async def ping(self) -> bool:
        return True


class RedisHubStore:
    """Redis-backed implementation for staging and production.

    Key schema: offer:{offer_id}  (string key, JSON value).
    No TTL set — Redis must use noeviction policy (C-002).
    Raises RedisUnavailableError on any connection failure.
    """

    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._redis_url = redis_url

    def _key(self, offer_id: str) -> str:
        return f"offer:{offer_id}"

    async def get(self, offer_id: str) -> Optional[OfferBrief]:
        try:
            raw = await self._redis.get(self._key(offer_id))
            if raw is None:
                return None
            return OfferBrief.model_validate_json(raw)
        except Exception as e:
            raise RedisUnavailableError(f"Redis GET failed: {e}") from e

    async def save(self, offer: OfferBrief) -> None:
        try:
            key = self._key(offer.offer_id)
            exists = await self._redis.exists(key)
            if exists:
                raise OfferAlreadyExistsError(f"Offer {offer.offer_id} already exists in Hub")
            await self._redis.set(key, offer.model_dump_json())
        except OfferAlreadyExistsError:
            raise
        except Exception as e:
            raise RedisUnavailableError(f"Redis SET failed: {e}") from e

    async def update(self, offer: OfferBrief) -> None:
        try:
            await self._redis.set(self._key(offer.offer_id), offer.model_dump_json())
        except Exception as e:
            raise RedisUnavailableError(f"Redis SET failed: {e}") from e

    async def list(
        self,
        status_filter: Optional[OfferStatus] = None,
        trigger_type: Optional[TriggerType] = None,
        since: Optional[datetime] = None,
    ) -> list[OfferBrief]:
        try:
            keys = await self._redis.keys("offer:*")
            if not keys:
                return []

            raw_values = await self._redis.mget(*keys)
            offers = []
            for raw in raw_values:
                if raw:
                    try:
                        offers.append(OfferBrief.model_validate_json(raw))
                    except Exception as parse_err:
                        logger.warning(f"hub_redis_parse_error: {parse_err}")

            if status_filter:
                offers = [o for o in offers if o.status == status_filter]
            if trigger_type:
                offers = [o for o in offers if o.trigger_type == trigger_type]
            if since:
                if since.tzinfo is None:
                    since = since.replace(tzinfo=timezone.utc)
                offers = [o for o in offers if o.created_at >= since]

            return offers
        except RedisUnavailableError:
            raise
        except Exception as e:
            raise RedisUnavailableError(f"Redis LIST failed: {e}") from e

    async def exists(self, offer_id: str) -> bool:
        try:
            return bool(await self._redis.exists(self._key(offer_id)))
        except Exception as e:
            raise RedisUnavailableError(f"Redis EXISTS failed: {e}") from e

    async def ping(self) -> bool:
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    async def validate_redis_config(self) -> None:
        """Check Redis maxmemory-policy — log CRITICAL if not noeviction."""
        try:
            config = await self._redis.config_get("maxmemory-policy")
            policy = config.get("maxmemory-policy", "unknown")
            if policy != "noeviction":
                logger.critical(
                    "redis_eviction_policy_misconfigured",
                    extra={"policy": policy, "expected": "noeviction"},
                )
        except Exception as e:
            logger.warning(f"redis_config_check_failed: {e}")
