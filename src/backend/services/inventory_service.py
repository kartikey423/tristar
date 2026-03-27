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
_STALE_THRESHOLD_HOURS = 24

_URGENCY_MAP = {
    "high": ("Clear {} overstock immediately — {} units in stock"),
    "medium": ("Promote {} to reduce excess inventory — {} units available"),
    "low": ("Gentle push on {} to maintain healthy stock levels"),
}


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

    def get_suggestions(self, limit: int = 3) -> list[InventorySuggestion]:
        """Return top N overstock items as AI-driven offer suggestions."""
        stale = self._is_stale()
        overstock = self.get_overstock_items()[:limit]

        suggestions = []
        for item in overstock:
            name = item["product_name"]
            units = int(item["units_in_stock"])
            urgency = item.get("urgency", "medium")

            template = _URGENCY_MAP.get(urgency, _URGENCY_MAP["medium"])
            objective = template.format(name, units)

            suggestions.append(
                InventorySuggestion(
                    product_id=item["product_id"],
                    product_name=name,
                    category=item["category"],
                    store=item["store"],
                    units_in_stock=units,
                    urgency=urgency,
                    suggested_objective=objective,
                    stale=stale,
                )
            )

        return suggestions
