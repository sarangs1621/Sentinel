import uuid

from pydantic import BaseModel, Field

from app.core.security import TokenType


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=2048)


class TokenPayload(BaseModel):
    sub: uuid.UUID
    type: TokenType
    jti: uuid.UUID | None = None
