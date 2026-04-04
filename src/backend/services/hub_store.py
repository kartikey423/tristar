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
    """Raised when an offer_id or source_deal_id already exists in the store."""


@runtime_checkable
class HubStore(Protocol):
    """Protocol defining the Hub storage interface."""

    async def get(self, offer_id: str) -> Optional[OfferBrief]: ...

    async def save(self, offer: OfferBrief) -> None:
        """Save a new offer. Raises OfferAlreadyExistsError if offer_id or source_deal_id already exists."""
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

    async def find_by_source_deal_id(self, source_deal_id: str) -> Optional[OfferBrief]: ...

    async def delete(self, offer_id: str) -> bool:
        """Delete an offer. Returns True if deleted, False if not found."""
        ...

    async def ping(self) -> bool:
        """Returns True if the store is healthy."""
        ...


def _apply_filters(
    offers: list[OfferBrief],
    status_filter: Optional[OfferStatus],
    trigger_type: Optional[TriggerType],
    since: Optional[datetime],
) -> list[OfferBrief]:
    """Apply optional list filters in-memory. Shared by both store implementations."""
    if status_filter:
        offers = [o for o in offers if o.status == status_filter]
    if trigger_type:
        offers = [o for o in offers if o.trigger_type == trigger_type]
    if since:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        offers = [o for o in offers if o.created_at >= since]
    return offers


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
        # Dedup by source_deal_id — prevents duplicate entries for the same deal/product
        if offer.source_deal_id is not None:
            _active = {OfferStatus.draft, OfferStatus.approved, OfferStatus.active}
            for existing in self._store.values():
                if (
                    existing.source_deal_id == offer.source_deal_id
                    and existing.status in _active
                ):
                    raise OfferAlreadyExistsError(
                        f"An offer for source_deal_id '{offer.source_deal_id}' "
                        f"already exists in Hub (offer_id={existing.offer_id}, status={existing.status.value})"
                    )
        self._store[offer.offer_id] = offer

    async def update(self, offer: OfferBrief) -> None:
        self._store[offer.offer_id] = offer

    async def list(
        self,
        status_filter: Optional[OfferStatus] = None,
        trigger_type: Optional[TriggerType] = None,
        since: Optional[datetime] = None,
    ) -> list[OfferBrief]:
        return _apply_filters(list(self._store.values()), status_filter, trigger_type, since)

    async def exists(self, offer_id: str) -> bool:
        return offer_id in self._store

    async def find_by_source_deal_id(self, source_deal_id: str) -> Optional[OfferBrief]:
        for offer in self._store.values():
            if offer.source_deal_id == source_deal_id:
                return offer
        return None

    async def delete(self, offer_id: str) -> bool:
        if offer_id in self._store:
            del self._store[offer_id]
            return True
        return False

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

    def _deal_key(self, source_deal_id: str) -> str:
        """Secondary index key mapping source_deal_id → offer_id."""
        return f"hub:deal:{source_deal_id}"

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
            # Dedup by source_deal_id — SET NX on secondary index before writing offer
            if offer.source_deal_id is not None:
                deal_inserted = await self._redis.set(
                    self._deal_key(offer.source_deal_id), offer.offer_id, nx=True
                )
                if deal_inserted is None:
                    raise OfferAlreadyExistsError(
                        f"An offer for source_deal_id '{offer.source_deal_id}' already exists in Hub"
                    )
            # SET NX is atomic: succeeds only if key does not exist (eliminates EXISTS+SET race)
            inserted = await self._redis.set(self._key(offer.offer_id), offer.model_dump_json(), nx=True)
            if inserted is None:
                # Roll back secondary index if primary write fails
                if offer.source_deal_id is not None:
                    await self._redis.delete(self._deal_key(offer.source_deal_id))
                raise OfferAlreadyExistsError(f"Offer {offer.offer_id} already exists in Hub")
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
            # Use SCAN (non-blocking cursor) instead of KEYS (blocks entire Redis keyspace)
            keys: list[str] = []
            async for key in self._redis.scan_iter("offer:*"):
                keys.append(key)

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

            return _apply_filters(offers, status_filter, trigger_type, since)
        except RedisUnavailableError:
            raise
        except Exception as e:
            raise RedisUnavailableError(f"Redis LIST failed: {e}") from e

    async def exists(self, offer_id: str) -> bool:
        try:
            return bool(await self._redis.exists(self._key(offer_id)))
        except Exception as e:
            raise RedisUnavailableError(f"Redis EXISTS failed: {e}") from e

    async def find_by_source_deal_id(self, source_deal_id: str) -> Optional[OfferBrief]:
        try:
            offer_id = await self._redis.get(self._deal_key(source_deal_id))
            if offer_id is None:
                return None
            return await self.get(offer_id)
        except RedisUnavailableError:
            raise
        except Exception as e:
            raise RedisUnavailableError(f"Redis deal lookup failed: {e}") from e

    async def delete(self, offer_id: str) -> bool:
        try:
            # Fetch offer to get source_deal_id for secondary index cleanup
            offer = await self.get(offer_id)
            result = await self._redis.delete(self._key(offer_id))
            if result > 0 and offer is not None and offer.source_deal_id is not None:
                await self._redis.delete(self._deal_key(offer.source_deal_id))
            return result > 0
        except RedisUnavailableError:
            raise
        except Exception as e:
            raise RedisUnavailableError(f"Redis DELETE failed: {e}") from e

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
