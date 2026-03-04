"""JWT authentication helpers and FastAPI dependency for current user."""

from datetime import datetime, timedelta
from typing import Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from database.connection import get_session
from database.models import User

# ---------------------------------------------------------------------------
# Config (loaded lazily so config_manager is available at import time)
# ---------------------------------------------------------------------------

_SECRET: Optional[str] = None

def _getSecret() -> str:
    global _SECRET
    if _SECRET is None:
        try:
            from config_manager import get_config
            _SECRET = get_config().get('jwtSecret', 'floosball-default-secret')
        except Exception:
            _SECRET = 'floosball-default-secret'
    return _SECRET


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# ---------------------------------------------------------------------------
# Password hashing (using bcrypt directly — passlib 1.x is incompatible with bcrypt 4+)
# ---------------------------------------------------------------------------

def verifyPassword(plainPassword: str, hashedPassword: str) -> bool:
    return _bcrypt.checkpw(plainPassword.encode(), hashedPassword.encode())


def hashPassword(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def createAccessToken(userId: int) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(userId), "exp": expire}
    return jwt.encode(payload, _getSecret(), algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

oauth2Scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def getCurrentUser(token: str = Depends(oauth2Scheme)) -> User:
    credentialsException = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _getSecret(), algorithms=[ALGORITHM])
        userId: Optional[str] = payload.get("sub")
        if userId is None:
            raise credentialsException
    except JWTError:
        raise credentialsException

    session = get_session()
    try:
        user = session.get(User, int(userId))
    finally:
        session.close()

    if user is None or not user.is_active:
        raise credentialsException
    return user
