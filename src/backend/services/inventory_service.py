"""Inventory service — loads CSV mock data and provides AI suggestion inputs."""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from src.backend.core.config import settings
from src.backend.models.offer_brief import InventorySuggestion

_OVERSTOCK_THRESHOLD = 500
_NEAR_EXPIRY_DAYS = 30        # items expiring within this many days are "near expiry"
_STALE_THRESHOLD_HOURS = 24

# Objectives for overstock items
_URGENCY_MAP = {
    "high": "Clear {} overstock immediately — {} units in stock at {} store",
    "medium": "Promote {} to reduce excess inventory — {} units available at {}",
    "low": "Gentle push on {} to maintain healthy stock levels at {}",
}

# Objectives for near-expiry seasonal items targeting older CTC loyalists
_NEAR_EXPIRY_TEMPLATE = (
    "Drive clearance of {} ({} units, {:.0f}% off recommended) at {} before season end — "
    "target active seniors and long-tenure CTC Triangle Rewards members within 5 km of store "
    "who purchase seasonal and home-care categories regularly"
)


class InventoryService:
    def __init__(self, file_path: Optional[str] = None) -> None:
        self._file_path = Path(file_path or settings.INVENTORY_FILE_PATH)
        self._items: list[dict] = []
        self._loaded_at: Optional[datetime] = None
        self._load()

    def _load(self) -> None:
        if not self._file_path.exists():
            logger.warning(f"Inventory file not found: {self._file_path}")
            return

        with open(self._file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self._items = list(reader)

        self._loaded_at = datetime.utcnow()
        logger.info(f"Loaded {len(self._items)} inventory items from {self._file_path}")

    def _is_stale(self) -> bool:
        if self._loaded_at is None:
            return True
        return datetime.utcnow() - self._loaded_at > timedelta(hours=_STALE_THRESHOLD_HOURS)

    def get_overstock_items(self) -> list[dict]:
        """Return items with units_in_stock > threshold, sorted by units descending."""
        overstock = [
            item for item in self._items
            if int(item.get("units_in_stock", 0)) > _OVERSTOCK_THRESHOLD
        ]
        return sorted(overstock, key=lambda x: int(x.get("units_in_stock", 0)), reverse=True)

    def get_near_expiry_items(self) -> list[dict]:
        """Return items with days_to_expiry between 1 and _NEAR_EXPIRY_DAYS, sorted soonest first."""
        near_expiry = []
        for item in self._items:
            days_raw = item.get("days_to_expiry", "-1")
            try:
                days = int(days_raw)
            except (ValueError, TypeError):
                days = -1
            if 0 < days <= _NEAR_EXPIRY_DAYS:
                near_expiry.append({**item, "_days_to_expiry": days})
        return sorted(near_expiry, key=lambda x: x["_days_to_expiry"])

    def get_suggestions(self, limit: int = 3) -> list[InventorySuggestion]:
        """Return top N suggestions prioritising near-expiry seasonal items, then overstock."""
        stale = self._is_stale()

        # Build a ranked candidate list: near-expiry first, then overstock
        near_expiry = self.get_near_expiry_items()
        overstock = [
            item for item in self.get_overstock_items()
            if item["product_id"] not in {n["product_id"] for n in near_expiry}
        ]

        candidates = (near_expiry + overstock)[:limit]

        suggestions = []
        for item in candidates:
            name = item["product_name"]
            units = int(item["units_in_stock"])
            urgency = item.get("urgency", "medium")
            store = item.get("store", "Canadian Tire")
            days = item.get("_days_to_expiry", -1)

            if days and days > 0:
                # Near-expiry: craft a senior-focused clearance objective
                discount_pct = 30.0 if urgency == "high" else 20.0 if urgency == "medium" else 10.0
                objective = _NEAR_EXPIRY_TEMPLATE.format(name, units, discount_pct, store)
            else:
                template = _URGENCY_MAP.get(urgency, _URGENCY_MAP["medium"])
                objective = template.format(name, units, store)

            suggestions.append(
                InventorySuggestion(
                    product_id=item["product_id"],
                    product_name=name,
                    category=item["category"],
                    store=store,
                    units_in_stock=units,
                    urgency=urgency,
                    suggested_objective=objective,
                    stale=stale,
                )
            )

        return suggestions
