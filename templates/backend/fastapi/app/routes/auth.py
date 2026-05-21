import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import create_token, hash_password, verify_password
from app.database import async_session
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthRequest(BaseModel):
    username: str
    password: str


class RegisterResponse(BaseModel):
    id: str
    username: str


class LoginResponse(BaseModel):
    token: str


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: AuthRequest) -> RegisterResponse:
    async with async_session() as session:
        existing = await session.execute(select(User).where(User.username == body.username))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username taken")

        user = User(
            id=uuid.uuid4(),
            username=body.username,
            password_hash=hash_password(body.password),
        )
        session.add(user)
        await session.commit()
        return RegisterResponse(id=str(user.id), username=user.username)


@router.post("/login", response_model=LoginResponse)
async def login(body: AuthRequest) -> LoginResponse:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == body.username))
        user = result.scalar_one_or_none()
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        token = create_token(str(user.id))
        return LoginResponse(token=token)
