from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from .schemas import UserCreate, UserLogin, TokenResponse, UserOut, RefreshRequest
from .service import AuthService
from .exceptions import (
    AccountDisabledError,
    AccountLockedError,
    DuplicateUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)


def get_auth_router(auth_service_dep: Callable[..., AuthService]) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
    async def register(payload: UserCreate, auth: AuthService = Depends(auth_service_dep)):
        try:
            return await auth.register(payload)
        except DuplicateUserError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    @router.post("/login", response_model=TokenResponse)
    async def login(payload: UserLogin, auth: AuthService = Depends(auth_service_dep)):
        try:
            return await auth.login(payload)
        except InvalidCredentialsError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
        except AccountLockedError as e:
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(e))
        except AccountDisabledError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    @router.post("/refresh", response_model=TokenResponse)
    async def refresh(payload: RefreshRequest, auth: AuthService = Depends(auth_service_dep)):
        try:
            return await auth.refresh(payload.refresh_token)
        except (InvalidTokenError, TokenExpiredError) as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    @router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(payload: RefreshRequest, auth: AuthService = Depends(auth_service_dep)):
        await auth.logout(payload.refresh_token)

    return router
