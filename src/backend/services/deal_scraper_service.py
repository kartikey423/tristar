"""Canadian Tire Deal Scraper Service — Haiku-Powered Intelligence

Architecture:
- Uses Claude 3.5 Haiku ($0.25/M tokens) for scraping intelligence
- Cache-buster: Force-refresh with timestamp parameter
- Randomization: Shuffles results for variety in Designer feed
- Rate limiting: 15-minute cache TTL to avoid blocking

Sources:
- https://www.canadiantire.ca/en/promotions/weekly-deals.html
- https://www.canadiantire.ca/en/flyer.html
- https://www.canadiantire.ca/en/promotions/clearance.html

Intelligence Strategy:
- Haiku extracts structured deals from raw HTML (no BeautifulSoup selectors needed)
- Prompt includes examples of deal patterns for few-shot learning
- Output is JSON array of {product_name, category, discount_pct, original_price, deal_price}
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta
from typing import Optional

import httpx
from anthropic import Anthropic
from loguru import logger

from src.backend.core.config import settings
from src.backend.models.offer_brief import DealSuggestion
from src.backend.services.hub_api_client import HubApiClient

# In-memory cache: URL → (deals, expires_at)
_deal_cache: dict[str, tuple[list[DealSuggestion], datetime]] = {}
_CACHE_TTL_MINUTES = 15  # Refresh every 15 minutes


class DealScraperService:
    """Scrape Canadian Tire deals using Haiku for intelligent HTML extraction."""

    def __init__(self, hub_client: Optional[HubApiClient] = None) -> None:
        self.urls = {
            "clearance": "https://www.canadiantire.ca/en/promotions/clearance.html",  # PRIMARY
            "weekly_deals": "https://www.canadiantire.ca/en/promotions/weekly-deals.html",
            "flyer": "https://www.canadiantire.ca/en/flyer.html",
        }
        self._http_client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )
        self._claude = Anthropic(api_key=settings.CLAUDE_API_KEY)
        self._hub = hub_client
        # Cache for approved deal IDs (5-minute TTL)
        self._approved_cache: tuple[set[str], datetime] | None = None

    async def fetch_deals(self) -> list[DealSuggestion]:
        """Fetch and parse deals from all Canadian Tire sources.

        Returns:
            List of DealSuggestion objects sorted by discount percentage (highest first).
        """
        all_deals: list[DealSuggestion] = []

        for source, url in self.urls.items():
            # Cache-buster: add timestamp to force fresh data
            cache_busted_url = f"{url}?_t={int(datetime.utcnow().timestamp())}"

            # Check cache first (15-minute TTL)
            cached = self._get_from_cache(url)
            if cached:
                all_deals.extend(cached)
                logger.debug(f"Cache hit for {source}: {len(cached)} deals")
                continue

            # Scrape URL using Haiku intelligence
            try:
                deals = await self._scrape_with_haiku(cache_busted_url, source, url)
                self._store_in_cache(url, deals)
                all_deals.extend(deals)
                logger.info(f"Scraped {len(deals)} deals from {source} using Haiku")
            except Exception as e:
                logger.warning(f"Failed to scrape {source}: {e}")
                # Use cached data if available (even expired)
                cached_stale = _deal_cache.get(url)
                if cached_stale:
                    all_deals.extend(cached_stale[0])
                    logger.info(f"Using stale cache for {source}")

        # Filter out deals that have been approved in Hub
        approved_ids = await self._get_approved_deal_ids()
        if approved_ids:
            before_count = len(all_deals)
            all_deals = [d for d in all_deals if d.deal_id not in approved_ids]
            filtered_count = before_count - len(all_deals)
            if filtered_count > 0:
                logger.info(f"Filtered {filtered_count} already-approved deals from feed")

        # Randomize for variety in Designer feed
        random.shuffle(all_deals)

        # Sort by discount percentage (highest first)
        all_deals.sort(key=lambda d: d.discount_pct, reverse=True)

        return all_deals

    async def _scrape_with_haiku(
        self, cache_busted_url: str, source: str, original_url: str
    ) -> list[DealSuggestion]:
        """Use Claude 3.5 Haiku to extract deals from raw HTML.

        Intelligence:
        - Haiku reads raw HTML and extracts deal structures
        - No fragile CSS selectors needed
        - Robust to Canadian Tire's JavaScript-rendered content
        """
        # Fetch raw HTML
        response = await self._http_client.get(cache_busted_url)
        response.raise_for_status()
        html = response.text

        # Truncate HTML to first 100KB (Haiku context limits)
        html_truncated = html[:100_000]

        # Haiku extraction prompt
        prompt = f"""Extract product deals from this Canadian Tire {source} page HTML.

Find products with visible discounts, sales, or promotional pricing. For each deal, extract:
- product_name: Full product name
- category: Product category (automotive, outdoor, appliances, tools, home, etc.)
- discount_pct: Discount percentage (calculate from original vs sale price)
- original_price: Regular price in CAD
- deal_price: Sale/promotional price in CAD

Return JSON array with 10-15 deals, sorted by highest discount first.

Example output:
[
  {{
    "product_name": "MotoMaster 20V Lithium-Ion Drill Kit",
    "category": "tools",
    "discount_pct": 40,
    "original_price": 149.99,
    "deal_price": 89.99
  }},
  ...
]

HTML content (truncated to 100KB):
{html_truncated}

Return ONLY the JSON array, no markdown formatting or explanation."""

        # Call Haiku for extraction
        try:
            message = self._claude.messages.create(
                model=settings.CLAUDE_MODEL_HAIKU,  # $0.25/M tokens
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse Haiku's JSON output
            content = message.content[0].text if message.content else "[]"

            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            import json

            raw_deals = json.loads(content.strip())

            # Convert to DealSuggestion objects
            deals: list[DealSuggestion] = []
            for raw in raw_deals:  # No hard cap — return all deals Haiku extracts
                try:
                    product_name = raw.get("product_name", "Unknown Product")
                    category = raw.get("category", "general")
                    discount_pct = float(raw.get("discount_pct", 0))
                    original_price = float(raw.get("original_price", 0))
                    deal_price = float(raw.get("deal_price", 0))

                    # Validate data
                    if not product_name or discount_pct <= 0 or deal_price <= 0:
                        continue

                    objective = self._generate_objective(product_name, discount_pct, category)

                    deals.append(
                        DealSuggestion(
                            deal_id=self._generate_deal_id(product_name, source),
                            product_name=product_name,
                            category=category.lower(),
                            discount_pct=round(discount_pct, 1),
                            original_price=round(original_price, 2),
                            deal_price=round(deal_price, 2),
                            source_url=original_url,
                            source=source,
                            suggested_objective=objective,
                            scraped_at=datetime.utcnow(),
                        )
                    )
                except (ValueError, KeyError, TypeError) as e:
                    logger.debug(f"Failed to parse deal from Haiku output: {e}")
                    continue

            return deals

        except Exception as e:
            logger.error(f"Haiku extraction failed for {source}: {e}")
            return []

    def _generate_objective(
        self, product_name: str, discount_pct: float, category: str
    ) -> str:
        """Generate marketing objective from deal details."""
        if discount_pct >= 40:
            return f"Drive clearance of {product_name} with {int(discount_pct)}% discount to {category} shoppers"
        elif discount_pct >= 25:
            return f"Promote {product_name} with aggressive {int(discount_pct)}% discount to active members"
        elif discount_pct >= 15:
            return f"Feature {product_name} in weekly deals for {category} enthusiasts"
        else:
            return f"Highlight {product_name} to increase {category} category awareness"

    def _generate_deal_id(self, product_name: str, source: str) -> str:
        """Generate deterministic deal ID from product name and source."""
        content = f"{source}:{product_name.lower()}"
        hash_hex = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"ctc-{source}-{hash_hex}"

    def _get_from_cache(self, url: str) -> Optional[list[DealSuggestion]]:
        """Get deals from cache if not expired."""
        entry = _deal_cache.get(url)
        if entry is None:
            return None

        deals, expires_at = entry
        if datetime.utcnow() > expires_at:
            del _deal_cache[url]
            return None

        return deals

    def _store_in_cache(self, url: str, deals: list[DealSuggestion]) -> None:
        """Store deals in cache with TTL."""
        expires_at = datetime.utcnow() + timedelta(minutes=_CACHE_TTL_MINUTES)
        _deal_cache[url] = (deals, expires_at)

    async def _get_approved_deal_ids(self) -> set[str]:
        """Get set of deal_ids that have been approved in Hub (cached for 5 minutes)."""
        if self._hub is None:
            return set()  # No deduplication if hub client not provided

        # Check cache (5-minute TTL)
        if self._approved_cache is not None:
            approved_ids, expires_at = self._approved_cache
            if datetime.utcnow() < expires_at:
                return approved_ids

        # Fetch all offers from Hub
        try:
            all_offers = await self._hub.get_all_offers()
            # Extract source_deal_id values (filter out None)
            approved_ids = {
                offer.source_deal_id
                for offer in all_offers
                if offer.source_deal_id is not None
            }

            # Cache result for 5 minutes
            self._approved_cache = (approved_ids, datetime.utcnow() + timedelta(minutes=5))

            logger.debug(f"Fetched {len(approved_ids)} approved deal IDs from Hub")
            return approved_ids

        except Exception as e:
            logger.warning(f"Failed to fetch approved deals from Hub: {e}")
            return set()  # On error, don't filter anything
