# FastAPI Standards

**Purpose:** Route structure, async patterns, and Pydantic models for TriStar backend
**Scope:** All Python code in `src/backend/`
**Enforcement:** Code review checks for FastAPI best practices

---

## Project Structure

```
src/backend/
├── main.py                  # FastAPI app entrypoint
├── api/                     # API routes
│   ├── designer.py         # Designer endpoints
│   ├── scout.py            # Scout endpoints
│   └── hub.py              # Hub endpoints
├── core/                    # Core config
│   ├── config.py           # Environment config
│   ├── deps.py             # Dependencies
│   └── security.py         # Auth/JWT
├── models/                  # Pydantic models
│   ├── offer_brief.py
│   ├── segment.py
│   └── context_signal.py
├── services/                # Business logic
│   ├── offer_generator.py
│   ├── fraud_detector.py
│   └── context_matcher.py
├── db/                      # Database
│   ├── base.py
│   ├── session.py
│   └── models.py           # SQLAlchemy models
└── utils/                   # Utilities
    ├── logging.py
    └── claude_api.py
```

---

## FastAPI Application Setup

### main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import designer, scout, hub
from app.core.config import settings
from app.db.session import engine
from app.utils.logging import setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    await engine.connect()
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(
    title="TriStar API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Routes
app.include_router(designer.router, prefix="/api/designer", tags=["designer"])
app.include_router(scout.router, prefix="/api/scout", tags=["scout"])
app.include_router(hub.router, prefix="/api/hub", tags=["hub"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

---

## Route Patterns

### Basic Route

```python
from fastapi import APIRouter, HTTPException, status
from app.models.offer_brief import OfferBriefRequest, OfferBriefResponse

router = APIRouter()

@router.post("/generate", response_model=OfferBriefResponse, status_code=status.HTTP_201_CREATED)
async def generate_offer_brief(request: OfferBriefRequest) -> OfferBriefResponse:
    """Generate OfferBrief from business objective using Claude API.

    Args:
        request: OfferBriefRequest with objective and segment criteria.

    Returns:
        Generated OfferBrief with segment, construct, channels, KPIs, and risk flags.

    Raises:
        HTTPException: 400 if validation fails, 500 if Claude API fails.
    """
    try:
        offer_brief = await offer_generator.generate(request)
        return offer_brief
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate offer brief: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### Route with Dependencies

```python
from fastapi import Depends
from app.core.deps import get_db, get_current_user

@router.get("/offers/{offer_id}", response_model=OfferBriefResponse)
async def get_offer(
    offer_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
) -> OfferBriefResponse:
    """Get offer by ID (authenticated users only)."""
    offer = await db.query(Offer).filter(Offer.offer_id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer
```

### Route with Background Task

```python
from fastapi import BackgroundTasks

async def send_notification(member_id: str, offer_id: str):
    # Send push notification
    await notification_service.send(member_id, offer_id)

@router.post("/activate", status_code=status.HTTP_202_ACCEPTED)
async def activate_offer(
    request: ActivateOfferRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Activate offer and send notification in background."""
    background_tasks.add_task(send_notification, request.member_id, request.offer_id)
    return {"status": "accepted", "message": "Notification queued"}
```

---

## Pydantic Models

### Request/Response Models

```python
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import List, Optional

class SegmentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    criteria: List[str] = Field(..., min_items=1, max_items=10)

    @validator('criteria')
    def validate_criteria(cls, v):
        allowed = ['high_value', 'lapsed', 'new_member', 'active']
        invalid = [c for c in v if c not in allowed]
        if invalid:
            raise ValueError(f"Invalid criteria: {invalid}")
        return v

class OfferBriefRequest(BaseModel):
    objective: str = Field(..., min_length=10, max_length=500)
    segment_criteria: List[str] = Field(..., min_items=1)

    class Config:
        json_schema_extra = {
            "example": {
                "objective": "Reactivate lapsed high-value members",
                "segment_criteria": ["high_value", "lapsed_90_days"]
            }
        }

class OfferBriefResponse(BaseModel):
    offer_id: str
    objective: str
    segment: SegmentRequest
    construct: dict
    channels: List[dict]
    kpis: dict
    risk_flags: dict
    created_at: datetime
    status: str

    class Config:
        from_attributes = True  # Pydantic v2 (was orm_mode in v1)
```

### Nested Models

```python
class Segment(BaseModel):
    name: str
    definition: str
    estimated_size: int
    criteria: List[str]

class Construct(BaseModel):
    type: str
    value: float
    description: str

class OfferBriefResponse(BaseModel):
    offer_id: str
    objective: str
    segment: Segment  # Nested model
    construct: Construct  # Nested model
    # ... rest
```

---

## Async Patterns

### Database Queries (Async)

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_offer_by_id(db: AsyncSession, offer_id: str) -> Optional[Offer]:
    stmt = select(Offer).where(Offer.offer_id == offer_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_active_offers(db: AsyncSession) -> List[Offer]:
    stmt = select(Offer).where(Offer.status == "active")
    result = await db.execute(stmt)
    return result.scalars().all()
```

### External API Calls (Async)

```python
import httpx

async def fetch_weather(lat: float, lon: float) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": WEATHER_API_KEY},
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()
```

### Concurrent Requests

```python
import asyncio

async def generate_offer_with_context(objective: str, member_id: str):
    # Fetch member data and weather in parallel
    member_data, weather_data = await asyncio.gather(
        fetch_member_data(member_id),
        fetch_weather(member.lat, member.lon),
    )

    # Generate offer with both contexts
    offer = await generate_offer(objective, member_data, weather_data)
    return offer
```

---

## Dependency Injection

### Database Dependency

```python
# app/core/deps.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_maker

async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
```

### Service Dependencies

```python
from app.services.offer_generator import OfferGenerator

async def get_offer_generator() -> OfferGenerator:
    return OfferGenerator(claude_api_key=settings.CLAUDE_API_KEY)

@router.post("/generate")
async def generate_offer(
    request: OfferBriefRequest,
    generator: OfferGenerator = Depends(get_offer_generator),
):
    return await generator.generate(request)
```

### Authentication Dependency

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthCredentials
import jwt

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

## Error Handling

### Custom Exception Classes

```python
class OfferNotFoundError(Exception):
    pass

class FraudDetectedError(Exception):
    def __init__(self, severity: str, details: dict):
        self.severity = severity
        self.details = details
```

### Global Exception Handler

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(OfferNotFoundError)
async def offer_not_found_handler(request: Request, exc: OfferNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": "OfferNotFoundError", "message": str(exc)},
    )

@app.exception_handler(FraudDetectedError)
async def fraud_detected_handler(request: Request, exc: FraudDetectedError):
    return JSONResponse(
        status_code=400,
        content={
            "error": "FraudDetectedError",
            "severity": exc.severity,
            "details": exc.details,
        },
    )
```

---

## Logging

### Structured Logging (loguru)

```python
from loguru import logger
import sys

def setup_logging():
    logger.remove()  # Remove default handler
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level=settings.LOG_LEVEL,
        serialize=True,  # JSON output
    )

# Usage
logger.info("Generating offer brief", extra={"objective": objective, "member_id": member_id})
logger.error("Claude API failed", extra={"error": str(e), "status_code": response.status_code})
```

### Request Logging Middleware

```python
import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    logger.info(
        "Request completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": int(duration * 1000),
        },
    )

    return response
```

---

## Configuration

### Settings with Pydantic

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "TriStar API"

    # Environment
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # External APIs
    CLAUDE_API_KEY: str
    WEATHER_API_KEY: str

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 1

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

---

## Testing

### Fixtures (Pytest)

```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
async def db_session():
    async with async_session_maker() as session:
        yield session
        await session.rollback()
```

### Route Tests

```python
@pytest.mark.asyncio
async def test_generate_offer_brief(client: AsyncClient):
    response = await client.post("/api/designer/generate", json={
        "objective": "Reactivate lapsed members",
        "segment_criteria": ["high_value", "lapsed_90_days"]
    })

    assert response.status_code == 201
    data = response.json()
    assert "offer_id" in data
    assert data["objective"] == "Reactivate lapsed members"
```

---

## OpenAPI Documentation

### Customize Schema

```python
@router.post(
    "/generate",
    response_model=OfferBriefResponse,
    summary="Generate OfferBrief",
    description="Generate structured OfferBrief from business objective using Claude API",
    responses={
        201: {"description": "OfferBrief created successfully"},
        400: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def generate_offer_brief(request: OfferBriefRequest):
    ...
```

### Access Docs
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

---

## Performance Best Practices

### Connection Pooling

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,  # Connection pool size
    max_overflow=20,  # Max connections above pool_size
    pool_pre_ping=True,  # Verify connections before using
)
```

### Caching with Redis

```python
import redis.asyncio as redis

redis_client = redis.from_url(settings.REDIS_URL)

async def get_cached_offer(offer_id: str) -> Optional[dict]:
    cached = await redis_client.get(f"offer:{offer_id}")
    if cached:
        return json.loads(cached)
    return None

async def cache_offer(offer_id: str, offer: dict, ttl: int = 300):
    await redis_client.setex(f"offer:{offer_id}", ttl, json.dumps(offer))
```

### Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/generate")
@limiter.limit("10/minute")
async def generate_offer_brief(request: Request, ...):
    ...
```

---

## Anti-Patterns to Avoid

### Don't Block with Sync Code

```python
# Bad (blocks event loop)
def generate_offer_sync(objective: str):
    time.sleep(5)  # Blocking!
    return offer

# Good (async)
async def generate_offer(objective: str):
    await asyncio.sleep(5)
    return offer
```

### Don't Use Global State

```python
# Bad (global mutable state)
offers_cache = {}

@router.post("/generate")
async def generate_offer(request: OfferBriefRequest):
    offers_cache[request.objective] = ...  # Race conditions!

# Good (use Redis or database)
@router.post("/generate")
async def generate_offer(request: OfferBriefRequest):
    await redis_client.set(f"offer:{objective}", ...)
```

### Don't Forget Error Handling

```python
# Bad (unhandled exception crashes server)
@router.get("/offers/{offer_id}")
async def get_offer(offer_id: str):
    return await db.query(Offer).filter(Offer.offer_id == offer_id).first()

# Good (handle errors)
@router.get("/offers/{offer_id}")
async def get_offer(offer_id: str):
    try:
        offer = await db.query(Offer).filter(Offer.offer_id == offer_id).first()
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")
        return offer
    except Exception as e:
        logger.error(f"Failed to fetch offer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

**Remember:** Always use async/await for I/O operations (database, external APIs) to avoid blocking the event loop