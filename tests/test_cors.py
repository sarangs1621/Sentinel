import pytest
from httpx import AsyncClient

from app.core.config import Settings


def test_wildcard_cors_origin_rejected() -> None:
    with pytest.raises(ValueError, match="BACKEND_CORS_ORIGINS"):
        Settings(BACKEND_CORS_ORIGINS=["*"])


@pytest.mark.asyncio(loop_scope="session")
async def test_cors_preflight_does_not_allow_wildcard(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/workspaces",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "*" not in response.headers["access-control-allow-methods"]
    assert "*" not in response.headers["access-control-allow-headers"]
