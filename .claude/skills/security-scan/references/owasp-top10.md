# OWASP Top 10 (2021) - TriStar Remediation

OWASP Top 10 web application security risks with TriStar-relevant remediation patterns.

---

## A01: Broken Access Control

**TriStar Risk:** Unauthorized access to offer management, bypassing approval workflow, accessing other members' data.

**Remediation:**
- JWT authentication on all Hub and Designer endpoints
- Role-based access: marketers can create/approve, scouts can only read approved offers
- Verify member_id ownership before returning member-specific data
- Deny by default: all routes require auth unless explicitly marked public
- Rate limit the generate endpoint to prevent abuse

---

## A02: Cryptographic Failures

**TriStar Risk:** API keys exposed, JWT secrets weak, data transmitted without encryption.

**Remediation:**
- All secrets stored in Azure Key Vault (production) or .env (development, gitignored)
- JWT secret minimum 256 bits, never default values in production
- HTTPS enforced in production (TLS 1.3)
- Claude API key never in client-side code, never logged
- Redis connections use TLS in production

---

## A03: Injection

**TriStar Risk:** SQL injection via offer search, prompt injection via Claude API, XSS via offer descriptions.

**Remediation:**
- SQL: use SQLAlchemy ORM or parameterized queries exclusively
- Prompt: sanitize user-provided objectives before inclusion in Claude API prompts
- XSS: React escapes output by default; never use raw HTML injection without DOMPurify
- Pydantic validation on all API inputs; Zod validation on all frontend inputs

---

## A04: Insecure Design

**TriStar Risk:** Missing fraud detection, Hub state machine bypass, rate limiting gaps.

**Remediation:**
- Threat modeling for each new feature (sdlc-risk skill)
- Fraud detection pipeline mandatory before approval
- Hub state machine enforced at service layer (not just API layer)
- Rate limiting at application level (not just API gateway)
- Security review as part of SDLC pipeline

---

## A05: Security Misconfiguration

**TriStar Risk:** Default CORS (wildcard), missing security headers, verbose error messages in production.

**Remediation:**
- CORS origins explicitly listed (no wildcard in production)
- Security headers: X-Content-Type-Options, X-Frame-Options, HSTS, CSP
- Error messages sanitized in production (no stack traces, no internal details)
- Debug mode disabled in production
- Default deny for all configurations

---

## A06: Vulnerable and Outdated Components

**TriStar Risk:** Known vulnerabilities in React, Next.js, FastAPI, or their dependencies.

**Remediation:**
- `npm audit` run before every PR (via scripts/security-scan.sh)
- `pip-audit` run before every PR
- Dependabot or equivalent configured for automatic updates
- Pin dependency versions in package.json and requirements.txt
- Block PRs with high/critical vulnerability findings

---

## A07: Identification and Authentication Failures

**TriStar Risk:** Weak JWT implementation, missing token expiry, token reuse.

**Remediation:**
- JWT tokens expire in 1 hour
- JWT algorithm: HS256 (symmetric) for dev, consider RS256 for production
- Token verification on every protected request via FastAPI Depends()
- Failed auth attempts logged (with member_id, not PII)
- No credential storage in browser localStorage (use httpOnly cookies)

---

## A08: Software and Data Integrity Failures

**TriStar Risk:** Tampered offer data, unsigned deployments, supply chain attacks.

**Remediation:**
- OfferBrief validated with Pydantic before any state transition
- Hub state transitions validated (no bypass of state machine)
- Git commit signing (if configured)
- SRI (Subresource Integrity) for CDN assets
- Lock files committed (package-lock.json, requirements.txt)

---

## A09: Security Logging and Monitoring Failures

**TriStar Risk:** Missing audit trail, PII in logs, undetected fraud.

**Remediation:**
- Structured logging with loguru (JSON format)
- Audit trail for all Hub state transitions (who, when, from_state, to_state)
- No PII in logs (member_id only)
- Failed authentication attempts logged
- Fraud detection results logged
- Monitor: offer activation rate, notification frequency, discount averages

---

## A10: Server-Side Request Forgery (SSRF)

**TriStar Risk:** Weather API URL manipulation, Redis connection string injection.

**Remediation:**
- Weather API URL hardcoded in configuration (not from user input)
- Redis URL from environment variable (validated format)
- Whitelist allowed external domains (openweathermap.org, api.anthropic.com)
- No user-controlled URLs in server-side requests
- Validate and sanitize any URL parameters
