import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import settings
from app.core.exceptions import AuthenticationError


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise AuthenticationError("Invalid or expired token")


async def get_user_by_id(user_id: uuid.UUID, session: AsyncSession) -> User | None:
    return await session.get(User, user_id)


async def register(email: str, password: str, session: AsyncSession) -> tuple[User, str]:
    existing = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing:
        raise AuthenticationError("Email already registered")
    user = User(email=email, password_hash=_hash_password(password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, create_token(user.id)


async def login(email: str, password: str, session: AsyncSession) -> tuple[User, str]:
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if not user or not _verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password")
    return user, create_token(user.id)
