from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import structlog
from sqlalchemy import or_, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from .config import AuthConfig
from .models import User, RefreshToken, OAuthAccount
from .schemas import UserCreate, UserLogin, TokenResponse, UserOut
from .security import SecurityManager
from .exceptions import (
    AccountDisabledError,
    AccountLockedError,
    DuplicateUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)

logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(self, config: AuthConfig, db: AsyncSession, audit_service: Optional[Any] = None):
        self.config = config
        self.db = db
        self.security = SecurityManager(config)
        self.audit_service = audit_service

    async def register(self, payload: UserCreate) -> User:
        user = User(
            username=payload.username,
            email=payload.email.lower(),
            password_hash=self.security.hash_password(payload.password),
        )
        self.db.add(user)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            logger.warning("registration_failed_duplicate", email=payload.email.lower(), username=payload.username)
            raise DuplicateUserError("Username or email already registered.")
        
        await self.db.refresh(user)
        logger.info("user_registered", user_id=user.id, email=user.email)
        
        if self.audit_service:
            await self.audit_service.log_action(
                action="user.registered",
                target_type="user",
                target_id=str(user.id),
                user_id=user.id,
                metadata={"email": user.email}
            )
            
        return user

    async def login(self, payload: UserLogin) -> TokenResponse:
        result = await self.db.execute(
            select(User).where(or_(User.username == payload.identifier, User.email == payload.identifier.lower()))
        )
        user = result.scalar_one_or_none()

        if user is None or user.password_hash is None:
            # Hash anyway to prevent timing attacks
            self.security.hash_password(payload.password)
            logger.warning("login_failed_invalid_user", identifier=payload.identifier)
            raise InvalidCredentialsError("Invalid credentials.")

        if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            logger.warning("login_failed_account_locked", user_id=user.id, locked_until=user.locked_until)
            raise AccountLockedError("Account temporarily locked.")

        if not self.security.verify_password(payload.password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= self.config.max_failed_logins:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=self.config.lockout_minutes)
                logger.warning("account_locked_limit_reached", user_id=user.id, attempts=user.failed_login_attempts)
                
                if self.audit_service:
                    await self.audit_service.log_action(
                        action="user.account_locked",
                        target_type="user",
                        target_id=str(user.id),
                        user_id=user.id,
                        metadata={"attempts": user.failed_login_attempts}
                    )
            await self.db.commit()
            logger.warning("login_failed_bad_password", user_id=user.id)
            raise InvalidCredentialsError("Invalid credentials.")

        if not user.is_active:
            logger.warning("login_failed_account_disabled", user_id=user.id)
            raise AccountDisabledError("Account disabled.")

        user.failed_login_attempts = 0
        user.locked_until = None
        await self.db.commit()

        logger.info("user_logged_in", user_id=user.id)
        
        if self.audit_service:
            await self.audit_service.log_action(
                action="user.login",
                target_type="user",
                target_id=str(user.id),
                user_id=user.id
            )
            
        return await self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        token_hash = self.security.hash_refresh_token(refresh_token)
        result = await self.db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        stored = result.scalar_one_or_none()

        if stored is None:
            logger.warning("refresh_failed_invalid_token")
            raise InvalidTokenError("Invalid refresh token.")

        if stored.revoked:
            logger.warning("refresh_token_replay_detected", user_id=stored.user_id)
            # Security measure: revoke all tokens for this user if a replay is detected
            await self.db.execute(update(RefreshToken).where(RefreshToken.user_id == stored.user_id).values(revoked=True))
            await self.db.commit()
            raise InvalidTokenError("Invalid refresh token.")

        if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            logger.info("refresh_failed_expired_token", user_id=stored.user_id)
            raise TokenExpiredError("Refresh token expired.")

        # Rotation: this token is single-use. Revoke it before issuing a new pair.
        stored.revoked = True
        
        result = await self.db.execute(select(User).where(User.id == stored.user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            await self.db.commit()
            logger.warning("refresh_failed_inactive_user", user_id=stored.user_id if stored else None)
            raise InvalidTokenError("Invalid refresh token.")

        token_response = await self._issue_tokens(user)
        
        # Cleanup old revoked/expired tokens to keep DB size down
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        await self.db.execute(
            delete(RefreshToken).where(
                RefreshToken.user_id == user.id,
                or_(RefreshToken.revoked == True, RefreshToken.expires_at < cutoff)
            )
        )
        await self.db.commit()
        logger.info("token_refreshed", user_id=user.id)
        return token_response

    async def logout(self, refresh_token: str) -> None:
        token_hash = self.security.hash_refresh_token(refresh_token)
        result = await self.db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        stored = result.scalar_one_or_none()
        if stored:
            stored.revoked = True
            await self.db.commit()
            logger.info("user_logged_out", user_id=stored.user_id)

    async def _issue_tokens(self, user: User) -> TokenResponse:
        access_token, expires_in = self.security.create_access_token(user.id)
        raw_refresh = self.security.generate_refresh_token()
        
        self.db.add(
            RefreshToken(
                user_id=user.id,
                token_hash=self.security.hash_refresh_token(raw_refresh),
                expires_at=self.security.get_refresh_token_expiry(),
            )
        )
        await self.db.commit()
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=expires_in
        )
