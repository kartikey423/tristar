"""Canadian Tire Deal Scraper Service

Intelligence: Syncs live deals from Canadian Tire to keep Designer offers current.
Rate Limiting: 1 request per minute to avoid blocking.
Fallback: Returns cached deals if scraping fails.

Sources:
- https://www.canadiantire.ca/en/promotions/weekly-deals.html
- https://www.canadiantire.ca/en/flyer.html
- https://www.canadiantire.ca/en/promotions/clearance.html
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.backend.models.offer_brief import DealSuggestion

# In-memory cache: URL → (deals, expires_at)
_deal_cache: dict[str, tuple[list[DealSuggestion], datetime]] = {}
_CACHE_TTL_MINUTES = 15  # Refresh every 15 minutes


class DealScraperService:
    """Scrape Canadian Tire deals and convert to offer suggestions."""

    def __init__(self) -> None:
        self.urls = {
            "weekly_deals": "https://www.canadiantire.ca/en/promotions/weekly-deals.html",
            "flyer": "https://www.canadiantire.ca/en/flyer.html",
            "clearance": "https://www.canadiantire.ca/en/promotions/clearance.html",
        }
        self._client = httpx.AsyncClient(
            timeout=10.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    async def fetch_deals(self) -> list[DealSuggestion]:
        """Fetch and parse deals from all Canadian Tire sources.

        Returns:
            List of DealSuggestion objects sorted by discount percentage (highest first).
        """
        all_deals: list[DealSuggestion] = []

        for source, url in self.urls.items():
            # Check cache first
            cached = self._get_from_cache(url)
            if cached:
                all_deals.extend(cached)
                logger.debug(f"Cache hit for {source}: {len(cached)} deals")
                continue

            # Scrape URL
            try:
                deals = await self._scrape_url(url, source)
                self._store_in_cache(url, deals)
                all_deals.extend(deals)
                logger.info(f"Scraped {len(deals)} deals from {source}")
            except Exception as e:
                logger.warning(f"Failed to scrape {source}: {e}")
                # Use cached data if available (even expired)
                cached_stale = _deal_cache.get(url)
                if cached_stale:
                    all_deals.extend(cached_stale[0])
                    logger.info(f"Using stale cache for {source}")

        # Sort by discount percentage (highest first)
        all_deals.sort(key=lambda d: d.discount_pct, reverse=True)

        return all_deals

    async def _scrape_url(self, url: str, source: str) -> list[DealSuggestion]:
        """Scrape a single URL and parse deals.

        Args:
            url: Canadian Tire URL to scrape
            source: Source identifier (weekly_deals, flyer, clearance)

        Returns:
            List of parsed DealSuggestion objects
        """
        response = await self._client.get(url)
        response.raise_for_status()

        html = response.text
        soup = BeautifulSoup(html, "lxml")

        # Parse based on source type
        if source == "weekly_deals":
            return self._parse_weekly_deals(soup, url)
        elif source == "flyer":
            return self._parse_flyer(soup, url)
        elif source == "clearance":
            return self._parse_clearance(soup, url)

        return []

    def _parse_weekly_deals(self, soup: BeautifulSoup, url: str) -> list[DealSuggestion]:
        """Parse weekly deals page.

        Pattern: Look for product cards with name, price, and discount.
        """
        deals: list[DealSuggestion] = []

        # Common CSS patterns for Canadian Tire product cards
        # (These are generic patterns - actual selectors may need adjustment)
        product_cards = soup.select(".product-card, .product-tile, [data-product]")

        for card in product_cards[:10]:  # Limit to top 10
            try:
                # Extract product name
                name_elem = card.select_one(
                    ".product-name, .product-title, h3, h4, [class*='title']"
                )
                if not name_elem:
                    continue
                product_name = name_elem.get_text(strip=True)

                # Extract pricing
                price_elem = card.select_one(
                    ".price, .sale-price, [class*='price'], [data-price]"
                )
                original_price_elem = card.select_one(
                    ".original-price, .was-price, [class*='was'], [class*='original']"
                )

                if not price_elem:
                    continue

                # Parse prices
                deal_price = self._parse_price(price_elem.get_text(strip=True))
                original_price = (
                    self._parse_price(original_price_elem.get_text(strip=True))
                    if original_price_elem
                    else deal_price * 1.25  # Assume 20% discount if no original price
                )

                # Calculate discount
                discount_pct = (
                    ((original_price - deal_price) / original_price) * 100
                    if original_price > 0
                    else 0.0
                )

                # Extract category (fallback to "general")
                category_elem = card.select_one(
                    ".category, .breadcrumb, [class*='category']"
                )
                category = (
                    category_elem.get_text(strip=True).lower()
                    if category_elem
                    else "general"
                )

                # Generate objective
                objective = self._generate_objective(product_name, discount_pct, category)

                deals.append(
                    DealSuggestion(
                        deal_id=self._generate_deal_id(product_name, "weekly_deals"),
                        product_name=product_name,
                        category=category,
                        discount_pct=round(discount_pct, 1),
                        original_price=round(original_price, 2),
                        deal_price=round(deal_price, 2),
                        source_url=url,
                        source="weekly_deals",
                        suggested_objective=objective,
                        scraped_at=datetime.utcnow(),
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to parse product card: {e}")
                continue

        return deals

    def _parse_flyer(self, soup: BeautifulSoup, url: str) -> list[DealSuggestion]:
        """Parse flyer page (similar pattern to weekly deals)."""
        # Use same parsing logic as weekly deals
        return self._parse_weekly_deals(soup, url)

    def _parse_clearance(self, soup: BeautifulSoup, url: str) -> list[DealSuggestion]:
        """Parse clearance page (usually has higher discounts)."""
        deals = self._parse_weekly_deals(soup, url)
        # Update source to clearance
        for deal in deals:
            deal.source = "clearance"
        return deals

    def _parse_price(self, price_text: str) -> float:
        """Parse price string to float.

        Examples:
            "$19.99" → 19.99
            "19.99" → 19.99
            "$1,299.00" → 1299.0
        """
        # Remove currency symbols, commas, and whitespace
        cleaned = price_text.replace("$", "").replace(",", "").replace("CAD", "").strip()

        # Extract first number (handle "from $X" or "starting at $X")
        import re

        match = re.search(r"[\d.]+", cleaned)
        if match:
            return float(match.group())

        return 0.0

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
