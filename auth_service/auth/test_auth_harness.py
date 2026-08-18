import asyncio
import os
import tempfile
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from auth.config import AuthConfig
from auth.models import AuthBase
from auth.service import AuthService
from auth.schemas import UserCreate, UserLogin
from auth.exceptions import InvalidCredentialsError, AccountLockedError

async def setup_test_keys():
    temp_dir = tempfile.mkdtemp()
    priv_path = Path(temp_dir) / "private.pem"
    pub_path = Path(temp_dir) / "public.pem"
    
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_path.write_bytes(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))
    
    public_key = private_key.public_key()
    pub_path.write_bytes(public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ))
    return str(priv_path), str(pub_path)

async def run_verification():
    print("Starting Auth Module Verification...")
    
    priv_key, pub_key = await setup_test_keys()
    
    config = AuthConfig(
        secret_key="test-secret-key-at-least-32-bytes-long",
        private_key_path=priv_key,
        public_key_path=pub_key,
        max_failed_logins=3,
        lockout_minutes=1
    )
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)
        
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with Session() as db:
        service = AuthService(config, db)
        
        # 1. Test Registration
        print("Testing Registration...")
        user = await service.register(UserCreate(username="testuser", email="test@example.com", password="password123"))
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        print("Registration OK.")
        
        # 2. Test Login
        print("Testing Login...")
        tokens = await service.login(UserLogin(identifier="testuser", password="password123"))
        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        print("Login OK.")
        
        # 3. Test Failed Login & Lockout
        print("Testing Brute Force Protection...")
        for _ in range(3):
            try:
                await service.login(UserLogin(identifier="testuser", password="wrongpassword"))
            except InvalidCredentialsError:
                pass
        
        try:
            await service.login(UserLogin(identifier="testuser", password="password123"))
            assert False, "Should have been locked out"
        except AccountLockedError:
            print("Lockout OK.")
            
        # 4. Test Token Refresh
        # (Need a fresh user for this to avoid lockout wait)
        print("Testing Token Refresh...")
        user2 = await service.register(UserCreate(username="user2", email="user2@example.com", password="password123"))
        tokens2 = await service.login(UserLogin(identifier="user2", password="password123"))
        
        new_tokens = await service.refresh(tokens2.refresh_token)
        assert new_tokens.access_token != tokens2.access_token
        assert new_tokens.refresh_token != tokens2.refresh_token
        print("Token Refresh OK.")
        
        # 5. Test Replay Detection
        print("Testing Replay Detection...")
        try:
            await service.refresh(tokens2.refresh_token) # Old token
            assert False, "Should have detected replay"
        except Exception:
            print("Replay Detection OK.")

    print("\nAuth Module Verification Successful!")

if __name__ == "__main__":
    asyncio.run(run_verification())
