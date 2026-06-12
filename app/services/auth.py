import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AccountLockedError, AuthenticationError, ConflictError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.token import Token
from app.schemas.user import UserCreate
from app.services.cache import CacheService


class AuthService:
    def __init__(self, session: AsyncSession, cache: CacheService | None = None) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.cache = cache if cache is not None else CacheService()

    async def register(self, data: UserCreate) -> User:
        existing = await self.users.get_by_email(data.email)
        if existing is not None:
            raise ConflictError("A user with this email already exists.")

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )
        self.users.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        if await self.cache.get_login_failure_count(email) >= settings.MAX_LOGIN_FAILURES:
            raise AccountLockedError("Too many failed login attempts. Please try again later.")

        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            await self.cache.record_login_failure(email)
            raise AuthenticationError("Incorrect email or password.")
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated.")

        await self.cache.reset_login_failures(email)
        return user

    async def login(self, email: str, password: str) -> Token:
        user = await self.authenticate(email, password)
        return await self._issue_token_pair(user.id)

    async def refresh(self, refresh_token: str) -> Token:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid or expired refresh token.") from exc

        if payload.get("type") != TokenType.REFRESH.value:
            raise AuthenticationError("Invalid token type.")

        try:
            token_id = uuid.UUID(payload["jti"])
            user_id = uuid.UUID(payload["sub"])
        except (KeyError, ValueError) as exc:
            raise AuthenticationError("Invalid token payload.") from exc

        stored = await self.refresh_tokens.get_active_by_id(token_id)
        if stored is None or stored.user_id != user_id:
            raise AuthenticationError("Refresh token has been revoked.")
        if stored.expires_at < datetime.now(UTC):
            raise AuthenticationError("Refresh token has expired.")

        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Account is no longer active.")

        # Rotation: revoke the presented token and issue a brand new pair.
        stored.revoked = True
        return await self._issue_token_pair(user.id)

    async def logout(self, refresh_token: str, access_token: str | None = None) -> None:
        if access_token is not None:
            await self._denylist_access_token(access_token)

        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError:
            return  # already invalid/expired -- nothing to revoke

        if payload.get("type") != TokenType.REFRESH.value:
            return

        try:
            token_id = uuid.UUID(payload["jti"])
        except (KeyError, ValueError):
            return

        stored = await self.refresh_tokens.get_by_id(token_id)
        if stored is not None and not stored.revoked:
            stored.revoked = True
            await self.session.commit()

    async def logout_all(self, user_id: uuid.UUID, access_token: str) -> None:
        """Revoke every active refresh token for `user_id` and denylist the
        presented access token, effectively signing the user out everywhere."""
        await self.refresh_tokens.revoke_all_for_user(user_id)
        await self.session.commit()
        await self._denylist_access_token(access_token)

    async def _denylist_access_token(self, access_token: str) -> None:
        try:
            payload = decode_token(access_token)
        except jwt.PyJWTError:
            return

        jti = payload.get("jti")
        if payload.get("type") == TokenType.ACCESS.value and jti is not None:
            await self.cache.denylist_token(jti, payload["exp"])

    async def _issue_token_pair(self, user_id: uuid.UUID) -> Token:
        token_record = RefreshToken(
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.refresh_tokens.add(token_record)
        await self.session.commit()
        await self.session.refresh(token_record)

        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id, token_record.id)
        return Token(access_token=access_token, refresh_token=refresh_token)
