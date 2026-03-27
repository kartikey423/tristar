# Backend Code Review Checklist

FastAPI / Python review checklist for TriStar project.

---

## 1. Type Hints
- [ ] All function parameters have type annotations
- [ ] All function return types annotated
- [ ] typing module used for complex types (List, Dict, Optional, Union)
- [ ] No implicit Any (all types explicit)
- [ ] Type hints match actual runtime behavior
- [ ] Pydantic models used for structured data (not plain dicts)

## 2. FastAPI Patterns
- [ ] All route handlers are async (`async def`, not `def`)
- [ ] Pydantic v2 models for request/response (BaseModel, not v1)
- [ ] `model_validator` and `field_validator` used (not deprecated `@validator`)
- [ ] `Depends()` for dependency injection (services, db, auth)
- [ ] `response_model` specified on route decorators
- [ ] Proper HTTP status codes (201 for create, 200 for get, 400 for validation, etc.)
- [ ] `BackgroundTasks` for fire-and-forget operations
- [ ] Lifespan context manager for startup/shutdown (not deprecated events)

## 3. Naming Conventions
- [ ] Variables and functions: snake_case
- [ ] Classes: PascalCase
- [ ] Constants: UPPER_SNAKE_CASE
- [ ] Modules/files: snake_case.py
- [ ] Test files: test_module_name.py
- [ ] Private methods prefixed with underscore
- [ ] No abbreviations that obscure meaning

## 4. Error Handling
- [ ] HTTPException with appropriate status codes
- [ ] Custom exception classes for domain errors
- [ ] No bare `except:` (always catch specific exceptions)
- [ ] No empty except blocks
- [ ] Error responses include useful message (not just status code)
- [ ] Exceptions logged with context before re-raising
- [ ] Global exception handlers registered for domain exceptions

## 5. Imports
- [ ] Import order: stdlib > third-party > local (isort compatible)
- [ ] No circular imports
- [ ] No unused imports
- [ ] `from __future__ import annotations` if needed for forward refs
- [ ] Specific imports (not `from module import *`)

## 6. Async Patterns
- [ ] All I/O operations use async/await (database, HTTP, Redis)
- [ ] No blocking sync code in async functions (no time.sleep, no sync file I/O)
- [ ] `asyncio.gather` for concurrent independent operations
- [ ] `httpx.AsyncClient` for HTTP requests (not requests library)
- [ ] Async context managers properly used (`async with`)
- [ ] No sync database calls in async routes

## 7. Data Validation (Pydantic v2)
- [ ] `Field()` with constraints (min_length, max_length, ge, le)
- [ ] `field_validator` for complex validation logic
- [ ] `model_validator` for cross-field validation
- [ ] `Config` class with `from_attributes = True` for ORM models
- [ ] `json_schema_extra` for API documentation examples
- [ ] Validation errors return clear messages

## 8. Logging
- [ ] loguru used (not stdlib logging or print)
- [ ] Structured logging with extra dict (not string interpolation in message)
- [ ] No PII in logs (member_id only, no names/emails/addresses)
- [ ] No print() statements
- [ ] Log levels appropriate (debug for development, info for business events, error for failures)
- [ ] Request context included in logs (endpoint, method, duration)

## 9. Security
- [ ] Parameterized queries only (no SQL string concatenation)
- [ ] Input validation via Pydantic (no trusting raw input)
- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] JWT verification on protected endpoints
- [ ] Rate limiting configured
- [ ] CORS origins restricted (not wildcard in production config)
- [ ] Environment variables via Pydantic BaseSettings

## 10. Testing
- [ ] Test file exists (test_module.py)
- [ ] `@pytest.mark.asyncio` on async tests
- [ ] `AsyncClient` for route testing (not sync TestClient)
- [ ] Fixtures for shared setup (db session, API client, sample data)
- [ ] External APIs mocked (Claude API, Weather API)
- [ ] `freezegun` for time-dependent tests
- [ ] Test naming: `test_what_when_condition_then_expected`

## 11. KISS and SOLID
- [ ] Functions have single responsibility
- [ ] No function exceeds 50 lines (extract helpers)
- [ ] No file exceeds 400 lines (split into modules)
- [ ] No premature optimization
- [ ] No dead code or commented-out code
- [ ] DRY without over-engineering

## 12. Performance
- [ ] Connection pooling configured for database
- [ ] Redis caching used where appropriate (with TTL)
- [ ] No N+1 query patterns
- [ ] Async gather for concurrent independent calls
- [ ] Response pagination for list endpoints
- [ ] No unnecessary data loading (select specific fields)
