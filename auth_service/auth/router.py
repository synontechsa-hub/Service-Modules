from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .exceptions import AccountDisabledError, AccountLockedError, DuplicateUserError, InvalidCredentialsError, InvalidTokenError, TokenExpiredError
from .models import User
from .schemas import RefreshRequest, TokenResponse, UserCreate, UserLogin, UserOut
from .service import AuthService

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_auth_router(auth_service_dep: Callable[..., AuthService]) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
    async def register(payload: UserCreate, auth: AuthService = Depends(auth_service_dep)) -> User:
        try:
            return await auth.register(payload)
        except DuplicateUserError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    @router.post("/login", response_model=TokenResponse)
    async def login(payload: UserLogin, auth: AuthService = Depends(auth_service_dep)) -> TokenResponse:
        try:
            return await auth.login(payload)
        except InvalidCredentialsError as exc:
            raise _unauthorized(str(exc)) from exc
        except AccountLockedError as exc:
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc)) from exc
        except AccountDisabledError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    @router.post("/refresh", response_model=TokenResponse)
    async def refresh(payload: RefreshRequest, auth: AuthService = Depends(auth_service_dep)) -> TokenResponse:
        try:
            return await auth.refresh(payload.refresh_token)
        except (InvalidTokenError, TokenExpiredError) as exc:
            raise _unauthorized(str(exc)) from exc

    @router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(payload: RefreshRequest, auth: AuthService = Depends(auth_service_dep)) -> None:
        await auth.logout(payload.refresh_token)

    return router


def get_current_user_dependency(auth_service_dep: Callable[..., AuthService]) -> Callable[..., User]:
    """Build a FastAPI dependency that resolves a Bearer access token to an active user."""
    async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer), auth: AuthService = Depends(auth_service_dep)) -> User:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise _unauthorized("Missing or invalid access token.")
        try:
            return await auth.user_from_access_token(credentials.credentials)
        except InvalidTokenError as exc:
            raise _unauthorized(str(exc)) from exc
    return current_user
