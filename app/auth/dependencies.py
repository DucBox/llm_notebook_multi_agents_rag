from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.models import User
from app.core.database import get_db
from app.core.exceptions import AuthenticationError

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    try:
        user_id = service.decode_token(credentials.credentials)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await service.get_user_by_id(user_id, session)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
