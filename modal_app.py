"""TriStar Modal Deployment - Cost-Optimized Serverless FastAPI

Infrastructure:
- Claude 3.5 Haiku for Scout Agent classification ($0.25/M tokens)
- Claude 3.5 Sonnet for offer generation ($3/M tokens)
- Prompt caching: 90% cost reduction on cached tokens
- Container idle timeout: 5 minutes
- Max timeout: 15 minutes

Deployment:
    modal token set --token-id MODAL_TOKEN_ID --token-secret MODAL_TOKEN_SECRET
    modal deploy modal_app.py

Cost Optimization:
- Observe: Monitor token usage via Anthropic console
- Think: Analyze classification vs generation patterns
- Act: Route to Haiku for scoring, Sonnet for generation
- Verify: Track cache hit rate (target >80%)
"""

import modal

# Modal image with Python 3.11 + all TriStar dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.30.0",
        "anthropic>=0.34.0",
        "redis>=5.0.0",
        "pydantic>=2.7.0",
        "pydantic-settings>=2.3.0",
        "httpx>=0.27.0",
        "python-jose[cryptography]>=3.3.0",
        "PyJWT>=2.8.0",
        "loguru>=0.7.2",
        "aiosqlite>=0.21.0",
        "sqlalchemy[asyncio]>=2.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=5.0.0",
    )
)

app = modal.App("tristar-api")


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_dict(
            {
                "CLAUDE_API_KEY": "REDACTED_ROTATE_THIS_KEY",
                "REDIS_URL": "redis://localhost:6379",
                "JWT_SECRET": "modal-production-secret-2026",
                "HUB_API_URL": "https://tristar-api.modal.run/api/hub",
                "DESIGNER_API_URL": "https://tristar-api.modal.run",
                "NOTIFICATION_PROVIDER_URL": "https://notification-service.modal.run",
                "MODAL_ENABLED": "true",
                "USE_PROMPT_CACHING": "true",
                "CLAUDE_MODEL_DEFAULT": "claude-3-5-sonnet-20241022",
                "CLAUDE_MODEL_HAIKU": "claude-3-5-haiku-20241022",
                "ENVIRONMENT": "production",
                "LOG_LEVEL": "INFO",
            }
        )
    ],
    timeout=900,  # 15 min max for long-running offer generation
    container_idle_timeout=300,  # 5 min idle before cold start
    cpu=2.0,  # 2 vCPUs for concurrent requests
    memory=2048,  # 2GB RAM
)
@modal.asgi_app()
def fastapi_app():
    """Mount TriStar FastAPI app with Modal infrastructure."""
    from src.backend.main import app as tristar_app

    return tristar_app


# Health check function for monitoring (removed to fix modal-http routing issue)
# The @modal.asgi_app() decorator provides all needed HTTP routing.
# Cron-based health checks can cause "invalid function call" errors when they
# try to invoke the ASGI app from within the same deployment context.


if __name__ == "__main__":
    print("TriStar Modal App")
    print("─" * 50)
    print("Deployment commands:")
    print("  1. Set credentials: modal token set --token-id <ID> --token-secret <SECRET>")
    print("  2. Deploy: modal deploy modal_app.py")
    print("  3. Test: curl https://tristar-api.modal.run/health")
    print("─" * 50)
    print("Cost optimization:")
    print("  • Haiku: $0.25/$1.25 per Mtok (classification)")
    print("  • Sonnet: $3/$15 per Mtok (generation)")
    print("  • Prompt caching: 90% reduction on cached tokens")
