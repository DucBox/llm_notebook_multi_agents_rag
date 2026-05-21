from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.core.database import get_db
from app.core.exceptions import AuthenticationError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_db)):
    try:
        user, token = await service.register(payload.email, payload.password, session)
    except AuthenticationError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return TokenResponse(access_token=token, user_id=user.id)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)):
    try:
        user, token = await service.login(payload.email, payload.password, session)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return TokenResponse(access_token=token, user_id=user.id)
