from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession, OptionalToken, oauth2_scheme
from app.schemas.token import RefreshTokenRequest, Token
from app.schemas.user import UserCreate, UserRead
from app.services.auth import AuthService

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: DbSession) -> UserRead:
    user = await AuthService(db).register(data)
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> Token:
    """OAuth2 password flow. `username` is the user's email address."""
    return await AuthService(db).login(form_data.username, form_data.password)


@router.post("/refresh", response_model=Token)
async def refresh(data: RefreshTokenRequest, db: DbSession) -> Token:
    return await AuthService(db).refresh(data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshTokenRequest, db: DbSession, access_token: OptionalToken = None) -> None:
    await AuthService(db).logout(data.refresh_token, access_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    current_user: CurrentUser,
    db: DbSession,
    access_token: Annotated[str, Depends(oauth2_scheme)],
) -> None:
    """Revoke all of the current user's refresh tokens and the presented access token."""
    await AuthService(db).logout_all(current_user.id, access_token)
