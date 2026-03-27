# pytest + httpx Patterns

Test patterns for TriStar backend code (FastAPI + Pydantic v2).

---

## Basic Function Test

```python
from app.services.context_matcher import calculate_context_score


def test_calculate_context_score_when_all_signals_available_then_returns_weighted_average():
    signals = {
        "gps": {"score": 80, "available": True},
        "time": {"score": 60, "available": True},
        "weather": {"score": 40, "available": True},
        "behavior": {"score": 90, "available": True},
    }

    result = calculate_context_score(signals)

    # GPS 30%, Time 25%, Weather 20%, Behavior 25%
    expected = (80 * 0.3) + (60 * 0.25) + (40 * 0.2) + (90 * 0.25)
    assert abs(result - expected) < 0.01


def test_calculate_context_score_when_gps_unavailable_then_redistributes_weights():
    signals = {
        "gps": {"score": 0, "available": False},
        "time": {"score": 60, "available": True},
        "weather": {"score": 40, "available": True},
        "behavior": {"score": 90, "available": True},
    }

    result = calculate_context_score(signals)

    assert 0 < result <= 100
```

---

## Async Route Test with AsyncClient

```python
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_generate_offer_brief_when_valid_input_then_returns_201(client: AsyncClient):
    response = await client.post(
        "/api/designer/generate",
        json={
            "objective": "Reactivate lapsed high-value members",
            "segment_criteria": ["high_value", "lapsed_90_days"],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "offer_id" in data
    assert data["objective"] == "Reactivate lapsed high-value members"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_generate_offer_brief_when_short_objective_then_returns_400(client: AsyncClient):
    response = await client.post(
        "/api/designer/generate",
        json={
            "objective": "short",
            "segment_criteria": ["high_value"],
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_generate_offer_brief_when_empty_segments_then_returns_400(client: AsyncClient):
    response = await client.post(
        "/api/designer/generate",
        json={
            "objective": "Reactivate lapsed high-value members",
            "segment_criteria": [],
        },
    )

    assert response.status_code == 400
```

---

## Pydantic Model Validation Test

```python
import pytest
from pydantic import ValidationError
from app.models.offer_brief import OfferBriefRequest, OfferBriefResponse


def test_offer_brief_request_when_valid_then_creates_model():
    request = OfferBriefRequest(
        objective="Reactivate lapsed high-value members",
        segment_criteria=["high_value", "lapsed_90_days"],
    )

    assert request.objective == "Reactivate lapsed high-value members"
    assert len(request.segment_criteria) == 2


def test_offer_brief_request_when_objective_too_short_then_raises_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        OfferBriefRequest(objective="short", segment_criteria=["high_value"])

    errors = exc_info.value.errors()
    assert any("objective" in str(e["loc"]) for e in errors)


def test_offer_brief_request_when_empty_segments_then_raises_validation_error():
    with pytest.raises(ValidationError):
        OfferBriefRequest(
            objective="Reactivate lapsed high-value members",
            segment_criteria=[],
        )
```

---

## Service Test with Mocked Dependencies

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.offer_generator import OfferGenerator
from app.models.offer_brief import OfferBrief


@pytest.fixture
def mock_claude_api():
    with patch("app.services.offer_generator.claude_api") as mock:
        mock.generate.return_value = {
            "segment": {"name": "lapsed_high_value", "criteria": ["high_value"]},
            "construct": {"type": "points_multiplier", "value": 5},
            "channels": [{"channel_type": "push", "priority": 1}],
            "kpis": {"expected_redemption_rate": 0.15},
        }
        yield mock


@pytest.mark.asyncio
async def test_offer_generator_when_valid_objective_then_returns_offer_brief(mock_claude_api):
    generator = OfferGenerator()
    result = await generator.generate("Reactivate lapsed members", ["high_value"])

    assert result.objective == "Reactivate lapsed members"
    assert result.status == "draft"
    mock_claude_api.generate.assert_called_once()
```

---

## Fixture Patterns

```python
import pytest
from httpx import AsyncClient
from app.main import app
from app.models.offer_brief import OfferBrief, Segment, Construct, KPIs, RiskFlags


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def db_session():
    from app.db.session import async_session_maker

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sample_offer_brief():
    return OfferBrief(
        offer_id="test-offer-123",
        objective="Reactivate lapsed high-value members",
        segment=Segment(
            name="lapsed_high_value",
            definition="Members inactive >90 days with LTV >$500",
            estimated_size=15000,
            criteria=["high_value", "lapsed_90_days"],
        ),
        construct=Construct(
            type="points_multiplier",
            value=5,
            description="5x points on next purchase",
        ),
        channels=[{"channel_type": "push", "priority": 1}],
        kpis=KPIs(expected_redemption_rate=0.15, expected_uplift_pct=25),
        risk_flags=RiskFlags(
            over_discounting=False,
            cannibalization=False,
            frequency_abuse=False,
            offer_stacking=False,
        ),
        status="draft",
    )


@pytest.fixture
def sample_context_signals():
    return {
        "gps": {"lat": 40.7128, "lon": -74.0060, "distance_km": 0.5},
        "time": {"hour": 14, "day_of_week": "wednesday"},
        "weather": {"condition": "sunny", "temp_c": 22},
        "behavior": {"last_purchase_days": 3, "avg_spend": 45.00},
    }
```

---

## freezegun for Time-Dependent Tests

```python
from freezegun import freeze_time


@freeze_time("2026-03-27 22:30:00")
def test_quiet_hours_when_10pm_then_blocks_notification():
    result = is_quiet_hours(timezone="America/New_York")
    assert result is True


@freeze_time("2026-03-27 08:00:00")
def test_quiet_hours_when_8am_then_allows_notification():
    result = is_quiet_hours(timezone="America/New_York")
    assert result is False


@freeze_time("2026-03-27 07:59:00")
def test_quiet_hours_when_just_before_8am_then_blocks_notification():
    result = is_quiet_hours(timezone="America/New_York")
    assert result is True
```

---

## AsyncMock for Claude API

```python
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_claude():
    mock = AsyncMock()
    mock.generate_offer_brief.return_value = {
        "offer_id": "gen-123",
        "segment": {"name": "lapsed_high_value"},
        "construct": {"type": "points_multiplier", "value": 5},
    }
    return mock


@pytest.mark.asyncio
async def test_designer_generate_when_claude_api_fails_then_retries(mock_claude):
    mock_claude.generate_offer_brief.side_effect = [
        Exception("API timeout"),
        Exception("API timeout"),
        {"offer_id": "gen-123", "segment": {"name": "test"}},  # Third attempt succeeds
    ]

    generator = OfferGenerator(claude_client=mock_claude)
    result = await generator.generate("Reactivate lapsed members", ["high_value"])

    assert mock_claude.generate_offer_brief.call_count == 3
    assert result is not None
```

---

## Test Naming Convention

```
test_<what>_when_<condition>_then_<expected>
```

Examples:
- `test_generate_offer_brief_when_valid_input_then_returns_draft_offer`
- `test_fraud_detector_when_discount_over_30_percent_then_flags_critical`
- `test_context_matcher_when_score_equals_60_then_activates`
- `test_hub_state_when_expired_to_active_then_rejects_transition`
- `test_notification_when_quiet_hours_then_queues_for_morning`
- `test_rate_limiter_when_second_notification_within_hour_then_blocks`
