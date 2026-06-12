import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_security_headers_present_on_response(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == "geolocation=(), microphone=(), camera=()"
    assert response.headers["Content-Security-Policy"] == "default-src 'none'"


async def test_csp_absent_on_docs(client: AsyncClient) -> None:
    response = await client.get("/docs")

    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers
    # Other security headers are still applied to the docs UI.
    assert response.headers["X-Content-Type-Options"] == "nosniff"


async def test_hsts_present_only_over_https() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        http_response = await http_client.get("/health")
    assert "Strict-Transport-Security" not in http_response.headers

    async with AsyncClient(transport=transport, base_url="https://test") as https_client:
        https_response = await https_client.get("/health")
    assert https_response.headers["Strict-Transport-Security"] == (
        f"max-age={settings.HSTS_MAX_AGE_SECONDS}; includeSubDomains"
    )


async def test_oversized_request_body_returns_413(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        content=b'{"email": "big@example.com", "password": "Password123!", "full_name": "Big"}',
        headers={
            "Content-Length": str(settings.MAX_REQUEST_BODY_BYTES + 1),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large."
