"""Unit tests for ClaudeApiService — COMP-004.

Key scenarios:
- Cache miss → calls Claude API
- Cache hit → returns DIFFERENT offer_id (F-001 fix)
- 3x retry on API failure
- Invalid JSON from Claude raises ClaudeResponseParseError
"""

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.backend.models.offer_brief import OfferBrief, TriggerType
from src.backend.services.claude_api import (
    ClaudeApiError,
    ClaudeApiService,
    ClaudeResponseParseError,
    _cache,
)

FIXTURES = json.loads(
    (Path(__file__).parents[3] / "fixtures/offer_brief_responses.json").read_text()
)
VALID_OFFER = FIXTURES["valid_marketer_offer"]


def make_claude_response(data: dict) -> MagicMock:
    """Create a mock Anthropic API response."""
    mock = MagicMock()
    mock.content = [MagicMock(text=json.dumps(data))]
    return mock


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear in-process cache before each test."""
    _cache.clear()
    yield
    _cache.clear()


_FAKE_API_KEY = "sk-ant-test-fake-key-000000000000"  # Fake key so _client is initialized


class TestCacheBehavior:
    async def test_cache_miss_calls_claude_api(self):
        """First call with an objective should hit Claude API."""
        service = ClaudeApiService(api_key=_FAKE_API_KEY)

        with patch.object(service, "_call_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = json.dumps(VALID_OFFER)
            offer = await service.generate_from_objective(
                "Reactivate lapsed high-value members with winter sports gear offer"
            )

        mock_call.assert_called_once()
        assert offer.offer_id  # UUID assigned

    async def test_cache_hit_returns_fresh_uuid(self):
        """F-001: cache hit must assign a fresh UUID, not return the cached offer_id."""
        objective = "Reactivate lapsed high-value members with winter sports gear offer"
        service = ClaudeApiService(api_key=_FAKE_API_KEY)

        with patch.object(service, "_call_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = json.dumps(VALID_OFFER)
            offer1 = await service.generate_from_objective(objective)

        # Second call — should hit cache
        with patch.object(service, "_call_with_retry", new_callable=AsyncMock) as mock_call2:
            offer2 = await service.generate_from_objective(objective)
            mock_call2.assert_not_called()  # Confirmed cache hit

        # F-001: different offer_ids despite same content
        assert offer1.offer_id != offer2.offer_id
        # Content is reused
        assert offer1.objective == offer2.objective
        assert offer1.segment.name == offer2.segment.name

    async def test_different_objectives_get_separate_cache_entries(self):
        service = ClaudeApiService(api_key=_FAKE_API_KEY)
        call_count = 0

        async def mock_call(prompt):
            nonlocal call_count
            call_count += 1
            return json.dumps(VALID_OFFER)

        with patch.object(service, "_call_with_retry", side_effect=mock_call):
            await service.generate_from_objective("Objective A for testing purposes here")
            await service.generate_from_objective("Objective B is different from above")

        assert call_count == 2

    async def test_cache_is_case_insensitive(self):
        """Cache key is SHA-256 of lowercase objective."""
        service = ClaudeApiService(api_key=_FAKE_API_KEY)

        with patch.object(service, "_call_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = json.dumps(VALID_OFFER)
            await service.generate_from_objective("CLEAR WINTER INVENTORY NOW PLEASE")

        with patch.object(service, "_call_with_retry", new_callable=AsyncMock) as mock_call2:
            await service.generate_from_objective("clear winter inventory now please")
            mock_call2.assert_not_called()


class TestRetryBehavior:
    async def test_retries_three_times_on_failure_then_raises(self):
        """API error should trigger 3 attempts total then raise ClaudeApiError."""
        import anthropic

        service = ClaudeApiService(api_key=_FAKE_API_KEY)
        call_count = 0

        def raise_api_error(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise anthropic.APIStatusError(
                "Rate limited",
                response=MagicMock(status_code=429),
                body={},
            )

        with patch.object(service._client.messages, "create", side_effect=raise_api_error):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ClaudeApiError):
                    await service._call_with_retry("test prompt")

        assert call_count == 3

    async def test_succeeds_on_second_attempt(self):
        """Should succeed if first attempt fails but second succeeds."""
        import anthropic

        service = ClaudeApiService(api_key=_FAKE_API_KEY)
        attempts = 0

        def flaky_call(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise anthropic.APIStatusError(
                    "Temporary error",
                    response=MagicMock(status_code=500),
                    body={},
                )
            return make_claude_response(VALID_OFFER)

        with patch.object(service._client.messages, "create", side_effect=flaky_call):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await service._call_with_retry("test prompt")

        assert result  # Got a response
        assert attempts == 2


class TestResponseParsing:
    def test_invalid_json_raises_parse_error(self):
        service = ClaudeApiService()
        with pytest.raises(ClaudeResponseParseError):
            service._parse_offer_brief("This is not JSON at all", TriggerType.marketer_initiated)

    def test_valid_json_returns_offer_brief(self):
        service = ClaudeApiService()
        result = service._parse_offer_brief(
            json.dumps(VALID_OFFER), TriggerType.marketer_initiated
        )
        assert isinstance(result, OfferBrief)

    def test_markdown_wrapped_json_is_extracted(self):
        service = ClaudeApiService()
        wrapped = f"```json\n{json.dumps(VALID_OFFER)}\n```"
        result = service._parse_offer_brief(wrapped, TriggerType.marketer_initiated)
        assert isinstance(result, OfferBrief)
