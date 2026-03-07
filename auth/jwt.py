# auth/jwt.py
# ═══════════════════════════════════════════════════════════
# JWT Authentication + Role-Based Access Control (RBAC)
# 3 Roles: admin, driver, customer
# ═══════════════════════════════════════════════════════════
import os
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from jose import jwt, JWTError
import bcrypt

from database import get_db
from models import User, UserRole

logger = logging.getLogger("fastdrop.auth")
router = APIRouter(prefix="/api/auth", tags=["Auth"])

# ── Config ────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(hours=24)
REFRESH_TOKEN_EXPIRE = timedelta(days=30)

security = HTTPBearer()


# ── Password Hashing (direct bcrypt — passlib broken on Python 3.13) ──
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ═══════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "customer"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    expires_in: int = 86400  # 24h in seconds


# ═══════════════════════════════════════════════
# JWT Token Utilities
# ═══════════════════════════════════════════════
def create_access_token(data: dict, expires_delta: timedelta = ACCESS_TOKEN_EXPIRE) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token (longer-lived)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + REFRESH_TOKEN_EXPIRE
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"التوكن غير صالح: {e}",
        )


# ═══════════════════════════════════════════════
# FastAPI Dependencies (Guards)
# ═══════════════════════════════════════════════
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency: extract current authenticated user from JWT."""
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "التوكن غير صالح — مفيش معرف مستخدم")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(401, "المستخدم مش موجود أو متعطل")
    return user


def require_role(*roles: UserRole):
    """Dependency factory: restrict access to specific roles."""
    async def role_check(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"مسموح فقط لـ: {[r.value for r in roles]}. أنت: {user.role.value}"
            )
        return user
    return role_check


# ═══════════════════════════════════════════════
# Auth Endpoints
# ═══════════════════════════════════════════════
@router.post("/register", response_model=TokenResponse)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    # Check if username or email already exists
    existing = await db.execute(
        select(User).where(
            (User.username == data.username) | (User.email == data.email)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "اسم المستخدم أو البريد موجود بالفعل")

    try:
        role = UserRole(data.role)
    except ValueError:
        role = UserRole.CUSTOMER

    hashed_pw = hash_password(data.password)

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hashed_pw,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token_data = {"sub": str(user.id), "role": user.role.value}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        role=user.role.value,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with username and password."""
    result = await db.execute(
        select(User).where(User.username == data.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "اسم المستخدم أو كلمة المرور غلط")

    if not user.is_active:
        raise HTTPException(403, "الحساب متعطل — تواصل مع الإدارة")

    token_data = {"sub": str(user.id), "role": user.role.value}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        role=user.role.value,
    )


@router.post("/refresh")
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Refresh access token using a valid refresh token."""
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "refresh":
        raise HTTPException(400, "لازم تستخدم refresh token مش access token")

    new_data = {"sub": payload["sub"], "role": payload["role"]}
    return {
        "access_token": create_access_token(new_data),
        "token_type": "bearer",
    }


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
    }
