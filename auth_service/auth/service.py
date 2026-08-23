import inspect
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Protocol

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import AuthConfig
from .exceptions import AccountDisabledError, AccountLockedError, DuplicateUserError, InvalidCredentialsError, InvalidTokenError, TokenExpiredError
from .models import RefreshToken, User
from .schemas import TokenResponse, UserCreate, UserLogin
from .security import SecurityManager

logger = logging.getLogger(__name__)


class AuditService(Protocol):
    def log_action(self, **kwargs: object) -> Awaitable[None] | None: ...


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AuthService:
    def __init__(self, config: AuthConfig, db: AsyncSession, audit_service: AuditService | None = None):
        self.config = config
        self.db = db
        self.security = SecurityManager(config)
        self.audit_service = audit_service

    async def _audit(self, **event: object) -> None:
        if self.audit_service is None:
            return
        try:
            result = self.audit_service.log_action(**event)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception("auth audit hook failed")

    async def register(self, payload: UserCreate) -> User:
        user = User(username=payload.username, email=str(payload.email).lower(), password_hash=self.security.hash_password(payload.password))
        self.db.add(user)
        try:
            await self.db.commit()
            await self.db.refresh(user)
        except IntegrityError as exc:
            await self.db.rollback()
            raise DuplicateUserError("Username or email already registered.") from exc
        except SQLAlchemyError:
            await self.db.rollback()
            raise
        await self._audit(action="user.registered", target_type="user", target_id=str(user.id), user_id=user.id)
        return user

    async def login(self, payload: UserLogin) -> TokenResponse:
        identifier = payload.identifier
        result = await self.db.execute(select(User).where(or_(User.username == identifier, User.email == identifier.lower())).with_for_update())
        user = result.scalar_one_or_none()
        if user is None or user.password_hash is None:
            self.security.burn_password_check(payload.password)
            raise InvalidCredentialsError("Invalid credentials.")

        now = datetime.now(timezone.utc)
        if user.locked_until and _utc(user.locked_until) > now:
            raise AccountLockedError("Account temporarily locked.")

        if not self.security.verify_password(payload.password, user.password_hash):
            user.failed_login_attempts += 1
            locked = user.failed_login_attempts >= self.config.max_failed_logins
            if locked:
                user.locked_until = now + timedelta(minutes=self.config.lockout_minutes)
            try:
                await self.db.commit()
            except SQLAlchemyError:
                await self.db.rollback()
                raise
            if locked:
                await self._audit(action="user.account_locked", target_type="user", target_id=str(user.id), user_id=user.id, metadata={"attempts": user.failed_login_attempts})
            raise InvalidCredentialsError("Invalid credentials.")

        if not user.is_active:
            raise AccountDisabledError("Account disabled.")

        user.failed_login_attempts = 0
        user.locked_until = None
        if self.security.password_needs_rehash(user.password_hash):
            user.password_hash = self.security.hash_password(payload.password)
        response = self._issue_tokens(user, family_id=uuid.uuid4())
        try:
            await self.db.commit()
        except SQLAlchemyError:
            await self.db.rollback()
            raise
        await self._audit(action="user.login", target_type="user", target_id=str(user.id), user_id=user.id)
        return response

    async def refresh(self, refresh_token: str) -> TokenResponse:
        token_hash = self.security.hash_refresh_token(refresh_token)
        result = await self.db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update())
        stored = result.scalar_one_or_none()
        if stored is None:
            raise InvalidTokenError("Invalid refresh token.")

        now = datetime.now(timezone.utc)
        if stored.revoked:
            await self._revoke_family(stored.user_id, stored.family_id, now)
            await self.db.commit()
            await self._audit(action="user.refresh_replay", target_type="user", target_id=str(stored.user_id), user_id=stored.user_id)
            raise InvalidTokenError("Invalid refresh token.")
        if _utc(stored.expires_at) <= now:
            raise TokenExpiredError("Refresh token expired.")

        result = await self.db.execute(select(User).where(User.id == stored.user_id).with_for_update())
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            stored.revoked = True
            stored.revoked_at = now
            await self.db.commit()
            raise InvalidTokenError("Invalid refresh token.")

        stored.revoked = True
        stored.revoked_at = now
        response = self._issue_tokens(user, family_id=stored.family_id)
        cutoff = now - timedelta(days=self.config.refresh_token_retention_days)
        await self.db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.expires_at < cutoff))
        try:
            await self.db.commit()
        except SQLAlchemyError:
            await self.db.rollback()
            raise
        return response

    async def logout(self, refresh_token: str) -> None:
        token_hash = self.security.hash_refresh_token(refresh_token)
        result = await self.db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update())
        stored = result.scalar_one_or_none()
        if stored is None or stored.revoked:
            return
        stored.revoked = True
        stored.revoked_at = datetime.now(timezone.utc)
        await self.db.commit()

    async def user_from_access_token(self, access_token: str) -> User:
        payload = self.security.decode_access_token(access_token)
        user_id = uuid.UUID(str(payload["sub"]))
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise InvalidTokenError("Invalid access token.")
        return user

    async def _revoke_family(self, user_id: uuid.UUID, family_id: uuid.UUID, now: datetime) -> None:
        await self.db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.family_id == family_id, RefreshToken.revoked.is_(False)).values(revoked=True, revoked_at=now))

    def _issue_tokens(self, user: User, family_id: uuid.UUID) -> TokenResponse:
        access_token, expires_in = self.security.create_access_token(user.id)
        raw_refresh = self.security.generate_refresh_token()
        self.db.add(RefreshToken(user_id=user.id, family_id=family_id, token_hash=self.security.hash_refresh_token(raw_refresh), expires_at=self.security.get_refresh_token_expiry()))
        return TokenResponse(access_token=access_token, refresh_token=raw_refresh, expires_in=expires_in)
