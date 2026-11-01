"""
Authentication utilities: password hashing and session management.

Uses bcrypt for password hashing and secure session cookies.
"""

from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets
from typing import Optional

# Password hashing (using argon2 for better compatibility)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_session_token() -> str:
    """Generate a secure random session token."""
    return secrets.token_urlsafe(32)


# Session token management (in production, use Redis or database)
_active_sessions = {}  # In-memory store for dev; use Redis in production


def create_session(user_id: int, expires_in_hours: int = 24) -> str:
    """
    Create a new session token for a user.

    Args:
        user_id: User ID
        expires_in_hours: Session expiration time in hours

    Returns:
        Session token
    """
    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

    _active_sessions[token] = {
        "user_id": user_id,
        "expires_at": expires_at,
    }

    return token


def get_session(token: str) -> Optional[dict]:
    """
    Retrieve a session by token.

    Args:
        token: Session token

    Returns:
        Session dict with user_id, or None if expired/invalid
    """
    if token not in _active_sessions:
        return None

    session = _active_sessions[token]

    # Check expiration
    if datetime.utcnow() > session["expires_at"]:
        del _active_sessions[token]
        return None

    return session


def invalidate_session(token: str) -> bool:
    """
    Invalidate a session token (logout).

    Args:
        token: Session token

    Returns:
        True if session was valid, False otherwise
    """
    if token in _active_sessions:
        del _active_sessions[token]
        return True
    return False


def cleanup_expired_sessions():
    """Remove expired sessions. Call periodically in background."""
    now = datetime.utcnow()
    expired = [
        token for token, session in _active_sessions.items()
        if now > session["expires_at"]
    ]
    for token in expired:
        del _active_sessions[token]
