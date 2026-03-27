# Azure Security Checklist

Azure-specific security requirements for TriStar deployment.

---

## Key Vault
- [ ] All secrets stored in Azure Key Vault (production)
- [ ] API keys accessed via managed identity or environment variables
- [ ] No secrets hardcoded in source code
- [ ] Secret rotation policy configured
- [ ] Access policies follow least-privilege principle
- [ ] Key Vault access logged and monitored

## App Service
- [ ] CORS restricted to specific origins (no wildcard in production)
- [ ] HTTPS enforced (HTTP redirects to HTTPS)
- [ ] TLS 1.2+ required (older versions disabled)
- [ ] Managed identity enabled for Azure service access
- [ ] Custom domain with valid SSL certificate
- [ ] IP restrictions configured if applicable

## Redis Cache
- [ ] Encrypted connections required (TLS)
- [ ] No plaintext credentials in connection strings
- [ ] Access via managed identity or Azure AD
- [ ] maxmemory-policy configured (noeviction for state data)
- [ ] Firewall rules restrict access to App Service only
- [ ] Persistence enabled (AOF or RDB) for Hub state data

## SQL Database
- [ ] Parameterized queries only (no string concatenation)
- [ ] Encrypted at rest (TDE enabled)
- [ ] Encrypted in transit (TLS required)
- [ ] Azure AD authentication (not SQL auth in production)
- [ ] Firewall rules restrict access
- [ ] Auditing enabled

## Azure Functions
- [ ] Managed identity for accessing other Azure services
- [ ] No inline secrets in function configuration
- [ ] CORS restricted
- [ ] Authentication configured (function keys or Azure AD)
- [ ] Timeout configured appropriately

## JWT Security
- [ ] Algorithm: HS256 (symmetric) or RS256 (asymmetric)
- [ ] Expiry: 1 hour maximum
- [ ] Secret: minimum 256 bits, stored in Key Vault
- [ ] Verification on every protected request
- [ ] Claims validated (sub, exp, iat)
- [ ] No sensitive data in JWT payload (member_id only, no PII)

## TriStar PII Requirements
- [ ] Only member_id in log statements
- [ ] No member names in any log output
- [ ] No member emails in any log output
- [ ] No member addresses in any log output
- [ ] No member phone numbers in any log output
- [ ] GPS coordinates not logged in plaintext
- [ ] Context signal raw data not persisted (only computed scores)
- [ ] Claude API prompts do not contain member PII

## Claude API Key Security
- [ ] Key stored in Key Vault (production) or .env (development)
- [ ] Key never appears in log output
- [ ] Key never in client-side code (frontend)
- [ ] Key never committed to git
- [ ] Key accessed via Pydantic BaseSettings
- [ ] Key rotation plan documented

## Rate Limiting
- [ ] API endpoints rate limited (slowapi or equivalent)
- [ ] Per-IP rate limiting on public endpoints
- [ ] Per-user rate limiting on authenticated endpoints
- [ ] Generate endpoint: 10 requests per minute
- [ ] Activate endpoint: rate limited per member (1/hr)
- [ ] Rate limit exceeded responses use 429 status code
