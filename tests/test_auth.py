import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import TokenType, decode_token
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from tests.conftest import DEFAULT_PASSWORD, auth_headers, login_user, register_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_register_creates_user(client: AsyncClient) -> None:
    data = await register_user(client, "alice@example.com")

    assert data["email"] == "alice@example.com"
    assert data["full_name"] == "Test User"
    assert data["is_active"] is True
    assert "hashed_password" not in data
    assert "id" in data


async def test_register_duplicate_email_fails(client: AsyncClient) -> None:
    await register_user(client, "bob@example.com")

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "bob@example.com", "password": DEFAULT_PASSWORD, "full_name": "Bob"},
    )

    assert response.status_code == 409


async def test_login_success_returns_token_pair(client: AsyncClient) -> None:
    await register_user(client, "carol@example.com")

    tokens = await login_user(client, "carol@example.com")

    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]


async def test_login_with_wrong_password_fails(client: AsyncClient) -> None:
    await register_user(client, "dave@example.com")

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "dave@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


async def test_get_current_user_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


async def test_get_current_user_returns_profile(client: AsyncClient) -> None:
    headers = await auth_headers(client, "erin@example.com")

    response = await client.get("/api/v1/users/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "erin@example.com"


async def test_refresh_token_rotation(client: AsyncClient) -> None:
    await register_user(client, "frank@example.com")
    tokens = await login_user(client, "frank@example.com")

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # The old refresh token was revoked by rotation and can no longer be used.
    reuse_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse_response.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    await register_user(client, "grace@example.com")
    tokens = await login_user(client, "grace@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=headers
    )
    assert logout_response.status_code == 204

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 401

    # The access token presented at logout is now denylisted.
    me_response = await client.get("/api/v1/users/me", headers=headers)
    assert me_response.status_code == 401


async def test_register_rejects_password_without_complexity(client: AsyncClient) -> None:
    digit_only = await client.post(
        "/api/v1/auth/register",
        json={"email": "digitonly@example.com", "password": "12345678", "full_name": "Weak"},
    )
    assert digit_only.status_code == 422

    letter_only = await client.post(
        "/api/v1/auth/register",
        json={"email": "letteronly@example.com", "password": "alllettersnodigits", "full_name": "Weak"},
    )
    assert letter_only.status_code == 422


async def test_login_lockout_after_max_failures(client: AsyncClient) -> None:
    await register_user(client, "locked@example.com")

    for _ in range(settings.MAX_LOGIN_FAILURES):
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "locked@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    locked_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "locked@example.com", "password": "wrong-password"},
    )
    assert locked_response.status_code == 423

    # The account stays locked even when the correct password is finally used.
    correct_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "locked@example.com", "password": DEFAULT_PASSWORD},
    )
    assert correct_response.status_code == 423


async def test_auth_endpoint_rate_limit_returns_429(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_REQUESTS", 3)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 60)

    for _ in range(3):
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


async def test_logout_all_revokes_all_sessions(client: AsyncClient) -> None:
    await register_user(client, "henry@example.com")
    session1 = await login_user(client, "henry@example.com")
    session2 = await login_user(client, "henry@example.com")
    headers1 = {"Authorization": f"Bearer {session1['access_token']}"}

    response = await client.post("/api/v1/auth/logout-all", headers=headers1)
    assert response.status_code == 204

    # Both refresh tokens issued before logout-all are revoked.
    for tokens in (session1, session2):
        refresh_response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert refresh_response.status_code == 401

    # The access token used to call logout-all is denylisted too.
    me_response = await client.get("/api/v1/users/me", headers=headers1)
    assert me_response.status_code == 401


async def test_login_rejects_deactivated_user(client: AsyncClient, db_session: AsyncSession) -> None:
    await register_user(client, "deactivated-login@example.com")

    user = await UserRepository(db_session).get_by_email("deactivated-login@example.com")
    assert user is not None
    user.is_active = False
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "deactivated-login@example.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 401


async def test_login_failures_reset_after_successful_login(client: AsyncClient) -> None:
    await register_user(client, "resetlock@example.com")

    # A few failed attempts, but not enough to trigger the lockout.
    for _ in range(settings.MAX_LOGIN_FAILURES - 1):
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "resetlock@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    # A successful login resets the failure counter.
    success_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "resetlock@example.com", "password": DEFAULT_PASSWORD},
    )
    assert success_response.status_code == 200

    # A single subsequent failure should not lock the account, since the counter was reset.
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "resetlock@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


# --- get_current_user edge cases ---


async def test_get_current_user_rejects_malformed_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401


async def test_get_current_user_rejects_refresh_token_as_access_token(client: AsyncClient) -> None:
    await register_user(client, "tokentype@example.com")
    tokens = await login_user(client, "tokentype@example.com")

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    assert response.status_code == 401


async def test_get_current_user_rejects_token_missing_sub(client: AsyncClient) -> None:
    payload = {
        "type": TokenType.ACCESS.value,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_get_current_user_rejects_token_for_unknown_user(client: AsyncClient) -> None:
    payload = {
        "sub": str(uuid.uuid4()),
        "type": TokenType.ACCESS.value,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_get_current_user_rejects_token_for_deactivated_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await register_user(client, "deactivated-current@example.com")
    tokens = await login_user(client, "deactivated-current@example.com")

    user = await UserRepository(db_session).get_by_email("deactivated-current@example.com")
    assert user is not None
    user.is_active = False
    await db_session.commit()

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 401


# --- refresh() edge cases ---


async def test_refresh_rejects_malformed_token(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-jwt"})
    assert response.status_code == 401


async def test_refresh_rejects_access_token_as_refresh_token(client: AsyncClient) -> None:
    await register_user(client, "refreshtype@example.com")
    tokens = await login_user(client, "refreshtype@example.com")

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert response.status_code == 401


async def test_refresh_rejects_token_missing_jti(client: AsyncClient) -> None:
    payload = {
        "sub": str(uuid.uuid4()),
        "type": TokenType.REFRESH.value,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(days=7),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401


async def test_refresh_rejects_unknown_token_id(client: AsyncClient) -> None:
    payload = {
        "sub": str(uuid.uuid4()),
        "type": TokenType.REFRESH.value,
        "jti": str(uuid.uuid4()),
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(days=7),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401


async def test_refresh_rejects_expired_stored_token(client: AsyncClient, db_session: AsyncSession) -> None:
    await register_user(client, "expiredrefresh@example.com")
    tokens = await login_user(client, "expiredrefresh@example.com")

    payload = decode_token(tokens["refresh_token"])
    stored = await RefreshTokenRepository(db_session).get_by_id(uuid.UUID(payload["jti"]))
    assert stored is not None
    stored.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401


async def test_refresh_rejects_deactivated_user(client: AsyncClient, db_session: AsyncSession) -> None:
    await register_user(client, "deactivatedrefresh@example.com")
    tokens = await login_user(client, "deactivatedrefresh@example.com")

    user = await UserRepository(db_session).get_by_email("deactivatedrefresh@example.com")
    assert user is not None
    user.is_active = False
    await db_session.commit()

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401


# --- logout() edge cases ---


async def test_logout_without_access_token_still_revokes_refresh(client: AsyncClient) -> None:
    await register_user(client, "logoutnoaccess@example.com")
    tokens = await login_user(client, "logoutnoaccess@example.com")

    response = await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 204

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 401


async def test_logout_with_malformed_refresh_token_returns_204(client: AsyncClient) -> None:
    await register_user(client, "logoutmalformed@example.com")
    tokens = await login_user(client, "logoutmalformed@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": "not-a-real-jwt"}, headers=headers
    )
    assert response.status_code == 204

    # The access token was still denylisted even though the refresh token was garbage.
    me_response = await client.get("/api/v1/users/me", headers=headers)
    assert me_response.status_code == 401


async def test_logout_with_access_token_as_refresh_token_returns_204(client: AsyncClient) -> None:
    await register_user(client, "logoutwrongtype@example.com")
    tokens = await login_user(client, "logoutwrongtype@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["access_token"]}, headers=headers
    )
    assert response.status_code == 204


async def test_logout_with_refresh_token_missing_jti_returns_204(client: AsyncClient) -> None:
    await register_user(client, "logoutnojti@example.com")
    tokens = await login_user(client, "logoutnojti@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    payload = {
        "sub": str(uuid.uuid4()),
        "type": TokenType.REFRESH.value,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(days=7),
    }
    fake_refresh = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": fake_refresh}, headers=headers
    )
    assert response.status_code == 204


async def test_logout_with_unknown_refresh_token_id_returns_204(client: AsyncClient) -> None:
    await register_user(client, "logoutunknownjti@example.com")
    tokens = await login_user(client, "logoutunknownjti@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    payload = {
        "sub": str(uuid.uuid4()),
        "type": TokenType.REFRESH.value,
        "jti": str(uuid.uuid4()),
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(days=7),
    }
    fake_refresh = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": fake_refresh}, headers=headers
    )
    assert response.status_code == 204


# --- _denylist_access_token edge cases ---


async def test_logout_with_malformed_access_token_returns_204(client: AsyncClient) -> None:
    await register_user(client, "logoutmalformedaccess@example.com")
    tokens = await login_user(client, "logoutmalformedaccess@example.com")

    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert response.status_code == 204

    # The refresh token was still revoked normally.
    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 401


async def test_logout_with_refresh_token_as_access_token_returns_204(client: AsyncClient) -> None:
    await register_user(client, "logoutrefreshasaccess@example.com")
    tokens = await login_user(client, "logoutrefreshasaccess@example.com")

    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert response.status_code == 204
