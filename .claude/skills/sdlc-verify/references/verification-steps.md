# Verification Steps

Detailed verification procedures adapted for TriStar's dual-stack architecture (TypeScript + Python).

---

## Step 1: File Existence Verification

### TypeScript Files (Frontend)
```
For each file in implementation_plan.md Wave 5-6:
  1. Glob for the file at its expected path
  2. If missing: mark as MISSING, add to critical findings
  3. If exists: read file, verify it has expected exports
```

### Python Files (Backend)
```
For each file in implementation_plan.md Wave 2-4:
  1. Glob for the file at its expected path
  2. If missing: mark as MISSING, add to critical findings
  3. If exists: read file, verify it has expected functions/classes
```

### Shared Types
```
For each file in implementation_plan.md Wave 1:
  1. Verify src/shared/types/ file exists
  2. Verify corresponding src/backend/models/ file exists
  3. Compare field names and types between Zod and Pydantic
```

---

## Step 2: Import and Dependency Verification

### TypeScript
```
For each component file:
  1. Grep for import statements
  2. Verify imported modules exist at referenced paths
  3. Check for circular imports (A imports B which imports A)
  4. Verify absolute imports use @ prefix (tsconfig paths)
  5. Check import order: React > third-party > internal > relative > types
```

### Python
```
For each module file:
  1. Grep for import/from statements
  2. Verify imported modules exist
  3. Check for circular imports
  4. Verify import order: stdlib > third-party > local (isort compatible)
  5. Check that async dependencies use async imports
```

---

## Step 3: Interface Contract Verification

### API Endpoints
```
For each API route in src/backend/api/:
  1. Read the route file
  2. Extract endpoint path, method, request model, response model
  3. Compare against design_spec.md API contracts
  4. Verify:
     - Path matches design
     - HTTP method matches design
     - Request model fields match design
     - Response model fields match design
     - Status codes handled match design
     - Auth requirements match design
```

### Component Props (React)
```
For each component in src/frontend/components/:
  1. Read the component file
  2. Extract props interface/type
  3. Compare against design_spec.md component interfaces
  4. Verify all required props are present
  5. Verify prop types match design
```

### Service Interfaces (Python)
```
For each service in src/backend/services/:
  1. Read the service file
  2. Extract public method signatures
  3. Compare against design_spec.md service interfaces
  4. Verify parameter types match
  5. Verify return types match
  6. Verify async/await usage
```

---

## Step 4: Pattern Compliance Verification

### React 19 Patterns
```
For each .tsx file:
  1. Check if 'use client' is present
     - If present: verify component uses hooks or browser APIs (justified)
     - If absent: verify no hooks or browser APIs used (Server Component)
  2. Check data fetching pattern
     - Grep for useEffect + fetch: FLAG as anti-pattern
     - Verify React.use() or async Server Component used instead
  3. Check for useOptimistic usage where design spec indicates optimistic updates
  4. Check Suspense boundaries around data-fetching components
```

### FastAPI Patterns
```
For each .py route file:
  1. Verify all route handlers are async (async def)
  2. Verify Depends() used for service injection (not direct instantiation)
  3. Verify Pydantic v2 models used (BaseModel with model_validator, not @validator)
  4. Verify response_model set on route decorators
  5. Verify proper status codes used
  6. Verify HTTPException for error cases
```

### 3-Layer Architecture
```
1. Grep src/backend/api/designer.py for imports from scout module: FLAG if found
2. Grep src/frontend/ for direct API calls to scout endpoints from designer pages: FLAG if found
3. Verify all inter-layer data flows through Hub:
   - Designer creates offers -> Hub stores them
   - Scout reads offers from Hub -> activates
   - No direct Designer -> Scout communication
```

---

## Step 5: Security Verification

### PII Check
```
1. Grep all .py and .ts files for common PII patterns:
   - member.name, member.email, member.address, member.phone
   - "name", "email" in logger.info/logger.error/console.log contexts
2. Verify only member_id appears in log statements
3. Check Claude API prompts for PII inclusion
4. Check GPS coordinates are not logged in plaintext
```

### Input Validation
```
1. For each API endpoint:
   - Verify Pydantic model validates request body
   - Check for Field validators on sensitive inputs
2. For each frontend form:
   - Verify Zod schema validates before submission
   - Check for XSS-prone patterns (raw innerHTML injection)
3. For database queries:
   - Verify parameterized queries or ORM (no string concatenation)
```

### Secrets
```
1. Grep for hardcoded API keys, tokens, passwords:
   - Pattern: sk-ant-, API_KEY=, password=, secret=, token=
2. Verify .env file is in .gitignore
3. Verify environment variables loaded via settings (Pydantic BaseSettings)
```

---

## Step 6: Test Coverage Analysis

### Frontend Tests
```
1. For each component in Wave 6:
   - Check if corresponding .test.tsx exists in tests/unit/frontend/
   - Read test file, count test cases
   - Verify screen.getByRole used (not getByTestId)
   - Verify waitFor used for async assertions
2. Run: npm test --coverage (if available)
3. Extract coverage percentage
```

### Backend Tests
```
1. For each service/route in Waves 3-4:
   - Check if corresponding test_*.py exists in tests/unit/backend/
   - Read test file, count test cases
   - Verify @pytest.mark.asyncio on async tests
   - Verify AsyncClient used for route tests
2. Run: pytest --cov=src/backend --cov-report=term-missing (if available)
3. Extract coverage percentage
```

### Integration Tests
```
1. Check tests/integration/ for cross-layer test files
2. Verify test scenarios cover:
   - Designer -> Hub flow
   - Hub -> Scout flow
   - End-to-end flow
3. Run: pytest tests/integration/ -m integration (if available)
```

---

## Step 7: Edge Case Verification

```
For each edge case from problem_spec.md:
  1. Search for test that covers this scenario:
     - Grep for keywords from the edge case description
     - Check boundary values in test data
  2. Search implementation code for handling:
     - Boundary checks (score == 60, discount == 30%)
     - Null/undefined handling
     - Empty collection handling
     - Timeout handling
  3. Mark as:
     - COVERED: test exists AND code handles
     - PARTIAL: only test OR only code handling
     - MISSING: neither test nor code handling
```

---

## Step 8: Domain-Specific Verification

### Fraud Detection
```
1. Locate fraud detection code (src/backend/services/fraud_detector.py)
2. Verify risk flag checks:
   - over_discounting: discount > 0.30 check present
   - cannibalization: segment overlap check present
   - frequency_abuse: offers per day count check present
   - offer_stacking: concurrent active offers count check present
3. Verify blocking behavior:
   - Grep for severity === 'critical' or severity == "critical"
   - Verify this condition blocks the state transition
4. Invoke loyalty-fraud-detection skill for comprehensive check
```

### Context Matching
```
1. Locate context matching code (src/backend/services/context_matcher.py)
2. Verify scoring logic:
   - GPS scoring ranges match tristar-patterns.md
   - Signal weights sum to 100%
   - Activation threshold is 60
3. Verify missing signal handling:
   - What happens when GPS unavailable?
   - What happens when weather API down?
4. Invoke semantic-context-matching skill for comprehensive check
```

### Rate Limiting
```
1. Locate notification/delivery code
2. Verify rate limit checks:
   - 1 notification per member per hour
   - 24h dedup for same offer
   - Quiet hours 10pm-8am
3. Verify queue behavior for rate-limited notifications
```
