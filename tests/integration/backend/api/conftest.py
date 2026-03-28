"""Shared fixtures for backend API integration tests."""

import pytest

from src.backend.api.deps import get_hub_store


@pytest.fixture(autouse=True)
def clear_hub_store_between_tests():
    """Wipe the in-memory Hub store before and after every integration test.

    Prevents test contamination when POST /generate auto-saves offers to Hub.
    """
    get_hub_store().clear()
    yield
    get_hub_store().clear()
