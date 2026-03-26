# Security Rules

**Purpose:** Security guidelines, input validation, secrets management, and OWASP top 10 for TriStar project
**Scope:** All frontend and backend code
**Enforcement:** Security scan before PR creation (blocks if critical vulnerabilities found)

---

## Critical Security Principles

1. **Never trust user input** - Validate and sanitize all inputs
2. **Never commit secrets** - Use environment variables and Azure Key Vault
3. **Never log PII** - Log member_id only, strip names/emails/addresses
4. **Always use HTTPS** - TLS 1.3 in production, no HTTP
5. **Always authenticate API requests** - JWT tokens with 1h expiry

---

## Input Validation

### Frontend (Zod)

**Validate ALL user inputs before sending to backend:**
```typescript
import { z } from 'zod';

const OfferBriefInputSchema = z.object({
  objective: z.string().min(10, 'Objective must be at least 10 characters').max(500),
  segment_criteria: z.array(z.string()).min(1, 'At least one segment criterion required'),
});

function validateInput(data: unknown) {
  try {
    return OfferBriefInputSchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ValidationError(error.errors);
    }
    throw error;
  }
}
```

**Patterns to reject:**
- SQL injection: `' OR '1'='1`, `'; DROP TABLE--`
- XSS: `<script>alert('xss')</script>`, `javascript:alert(1)`
- Path traversal: `../../../etc/passwd`
- Command injection: `; rm -rf /`, `| cat /etc/passwd`

### Backend (Pydantic)

**Validate at API boundary:**
```python
from pydantic import BaseModel, Field, validator

class OfferBriefRequest(BaseModel):
    objective: str = Field(..., min_length=10, max_length=500)
    segment_criteria: list[str] = Field(..., min_items=1, max_items=10)

    @validator('objective')
    def validate_objective(cls, v):
        # Reject SQL injection patterns
        if any(pattern in v.lower() for pattern in ["drop table", "select *", "' or '", "union select"]):
            raise ValueError("Invalid characters in objective")

        # Reject XSS patterns
        if any(tag in v.lower() for tag in ["<script", "javascript:", "onerror="]):
            raise ValueError("Invalid characters in objective")

        return v
```

---

## Secrets Management

### Development (.env file)

**Create `.env` (gitignored):**
```bash
CLAUDE_API_KEY=sk-ant-api03-...
WEATHER_API_KEY=...
DATABASE_URL=sqlite:///tristar.db
REDIS_URL=redis://localhost:6379
JWT_SECRET=dev-secret-change-in-prod
LOG_LEVEL=DEBUG
ENVIRONMENT=development
```

**Load with python-dotenv:**
```python
from dotenv import load_dotenv
import os

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
if not CLAUDE_API_KEY:
    raise ValueError("CLAUDE_API_KEY environment variable not set")
```

### Production (Azure Key Vault)

**Store secrets in Key Vault:**
```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://tristar-kv.vault.azure.net/", credential=credential)

CLAUDE_API_KEY = client.get_secret("claude-api-key").value
```

**Never log secrets:**
```python
# Good
logger.info(f"Calling Claude API", extra={"model": "claude-sonnet-4-6"})

# Bad
logger.info(f"Calling Claude API with key {CLAUDE_API_KEY}")
```

---

## Authentication & Authorization

### JWT Tokens

**Generate token (login):**
```python
import jwt
from datetime import datetime, timedelta

def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")
```

**Verify token (middleware):**
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Protected routes:**
```python
@router.get("/api/hub/offers")
async def get_offers(user_id: str = Depends(verify_token)):
    # Only authenticated users can access
    return await fetch_offers(user_id)
```

---

## CORS Configuration

### Development (Allow localhost)
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

### Production (Specific origins)
```python
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # ["https://tristar.azurewebsites.net"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

**Never use `allow_origins=["*"]` in production**

---

## SQL Injection Prevention

### Use Parameterized Queries
```python
# Good (parameterized)
async def get_offer_by_id(offer_id: str):
    query = "SELECT * FROM offers WHERE offer_id = ?"
    return await db.fetch_one(query, (offer_id,))

# Bad (string concatenation)
async def get_offer_by_id(offer_id: str):
    query = f"SELECT * FROM offers WHERE offer_id = '{offer_id}'"
    return await db.fetch_one(query)  # Vulnerable to SQL injection!
```

### Use ORM (SQLAlchemy)
```python
from sqlalchemy import select

async def get_offer_by_id(offer_id: str):
    stmt = select(Offer).where(Offer.offer_id == offer_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
```

---

## XSS Prevention

### Frontend (React)

**React escapes by default (safe):**
```tsx
<div>{userInput}</div> {/* Safe: React escapes HTML */}
```

**Dangerous (avoid):**
```tsx
<div dangerouslySetInnerHTML={{ __html: userInput }} /> {/* UNSAFE! */}
```

**Sanitize HTML if needed:**
```typescript
import DOMPurify from 'dompurify';

function SafeHTML({ html }: { html: string }) {
  const sanitized = DOMPurify.sanitize(html);
  return <div dangerouslySetInnerHTML={{ __html: sanitized }} />;
}
```

### Backend

**Escape HTML before logging:**
```python
import html

def sanitize_for_log(text: str) -> str:
    return html.escape(text)

logger.info(f"User input: {sanitize_for_log(user_input)}")
```

---

## Rate Limiting

### API Gateway (Azure API Management)
```xml
<policies>
    <inbound>
        <rate-limit-by-key calls="100" renewal-period="60" counter-key="@(context.Request.IpAddress)" />
    </inbound>
</policies>
```

### Application Level (FastAPI)
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/api/designer/generate")
@limiter.limit("10/minute")
async def generate_offer_brief(request: Request, ...):
    ...
```

---

## PII Handling

### Never Log PII
```python
# Good (log member_id only)
logger.info(f"Generating offer for member", extra={"member_id": member.member_id})

# Bad (logs PII)
logger.info(f"Generating offer for {member.name} ({member.email})")
```

### Anonymize in Logs
```python
def anonymize_member(member: Member) -> dict:
    return {
        "member_id": member.member_id,
        "segment": member.segment,
        # Do NOT include: name, email, address, phone
    }

logger.info("Member data", extra=anonymize_member(member))
```

### Mask in Database Logs
```python
# If logging SQL queries, mask sensitive fields
query = "INSERT INTO members (member_id, name, email) VALUES (?, '[REDACTED]', '[REDACTED]')"
```

---

## HTTPS Enforcement

### Production (Azure App Service)
```python
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
```

### Set Secure Headers
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import Response

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

---

## Dependency Scanning

### Frontend (npm audit)
```bash
npm audit --audit-level=moderate
npm audit fix
```

### Backend (pip-audit)
```bash
pip install pip-audit
pip-audit
```

**Block PRs if high/critical vulnerabilities found**

---

## Security Checklist

### Before Committing Code
- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user inputs validated (Zod frontend, Pydantic backend)
- [ ] No SQL string concatenation (use parameterized queries)
- [ ] No `dangerouslySetInnerHTML` without sanitization
- [ ] PII not logged (member_id only)
- [ ] Dependencies up-to-date (`npm audit`, `pip-audit`)

### Before Creating PR
- [ ] Security scan passes (no critical vulnerabilities)
- [ ] HTTPS enforced in production config
- [ ] CORS restricted to specific origins (not `*`)
- [ ] Rate limiting configured
- [ ] JWT tokens expire in 1h
- [ ] All secrets in environment variables or Key Vault

### Before Production Deploy
- [ ] All .env files gitignored
- [ ] Secrets migrated to Azure Key Vault
- [ ] TLS 1.3 enabled
- [ ] Security headers set (CSP, HSTS, X-Frame-Options)
- [ ] Database backups enabled
- [ ] Monitoring/alerts configured (failed auth attempts, rate limit exceeded)

---

## OWASP Top 10 Compliance

| OWASP Risk | Mitigation |
|------------|------------|
| **A01: Broken Access Control** | JWT tokens, role-based authorization |
| **A02: Cryptographic Failures** | TLS 1.3, Azure Key Vault for secrets |
| **A03: Injection** | Parameterized queries, Pydantic validation |
| **A04: Insecure Design** | Threat modeling, security reviews |
| **A05: Security Misconfiguration** | Azure security baseline, default-deny CORS |
| **A06: Vulnerable Components** | npm audit, pip-audit, Dependabot |
| **A07: Authentication Failures** | JWT tokens, 1h expiry, strong passwords |
| **A08: Software & Data Integrity** | Git commit signing, SRI for CDN assets |
| **A09: Logging Failures** | Structured logging, no PII, audit trail |
| **A10: SSRF** | Validate URLs, whitelist domains for Weather API |

---

## Incident Response

### If Secret Leaked to Git
1. **Rotate immediately** (regenerate API key)
2. **Revoke old key** (invalidate compromised token)
3. **Audit logs** (check for unauthorized access)
4. **Notify team** (post in Slack/Teams)

### If Vulnerability Found
1. **Assess severity** (CVSS score)
2. **Patch immediately** if critical
3. **Test patch** in staging before prod
4. **Document** in security log

---

**Remember:** Security is everyone's responsibility—not just DevOps or InfoSec