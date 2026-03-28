"""Unit tests for InventoryService — COMP-005."""

import csv
import tempfile
from pathlib import Path

import pytest

from src.backend.services.inventory_service import InventoryService, _OVERSTOCK_THRESHOLD


@pytest.fixture
def inventory_csv(tmp_path):
    """Create a temporary inventory CSV for testing."""
    csv_path = tmp_path / "test_inventory.csv"
    rows = [
        {
            "product_id": "P001",
            "product_name": "Winter Jacket",
            "category": "outerwear",
            "store": "Sport Chek",
            "units_in_stock": "620",
            "reorder_point": "100",
            "unit_price": "249.99",
            "urgency": "high",
        },
        {
            "product_id": "P002",
            "product_name": "Running Shoes",
            "category": "footwear",
            "store": "Sport Chek",
            "units_in_stock": "540",
            "reorder_point": "150",
            "unit_price": "129.99",
            "urgency": "high",
        },
        {
            "product_id": "P003",
            "product_name": "Work Boots",
            "category": "footwear",
            "store": "Mark's",
            "units_in_stock": "45",  # Below threshold
            "reorder_point": "120",
            "unit_price": "189.99",
            "urgency": "low",
        },
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


class TestInventoryService:
    def test_returns_top_3_overstock_items(self, inventory_csv):
        service = InventoryService(file_path=str(inventory_csv))
        suggestions = service.get_suggestions(limit=3)
        # Only P001 (620) and P002 (540) exceed threshold; P003 (45) does not
        assert len(suggestions) == 2

    def test_low_stock_items_excluded(self, inventory_csv):
        service = InventoryService(file_path=str(inventory_csv))
        suggestions = service.get_suggestions()
        product_ids = [s.product_id for s in suggestions]
        assert "P003" not in product_ids  # 45 units — below threshold

    def test_overstock_items_sorted_by_units_descending(self, inventory_csv):
        service = InventoryService(file_path=str(inventory_csv))
        overstock = service.get_overstock_items()
        assert int(overstock[0]["units_in_stock"]) >= int(overstock[-1]["units_in_stock"])

    def test_suggestion_has_suggested_objective(self, inventory_csv):
        service = InventoryService(file_path=str(inventory_csv))
        suggestions = service.get_suggestions()
        for s in suggestions:
            assert len(s.suggested_objective) > 0
            assert s.product_name in s.suggested_objective

    def test_stale_false_when_recently_loaded(self, inventory_csv):
        service = InventoryService(file_path=str(inventory_csv))
        suggestions = service.get_suggestions()
        # Just loaded — should NOT be stale
        for s in suggestions:
            assert s.stale is False

    def test_stale_true_when_file_not_found(self, tmp_path):
        service = InventoryService(file_path=str(tmp_path / "missing.csv"))
        # File not found — no items loaded, stale
        assert service._is_stale() is True

    def test_limit_respected(self, inventory_csv):
        service = InventoryService(file_path=str(inventory_csv))
        suggestions = service.get_suggestions(limit=1)
        assert len(suggestions) <= 1
