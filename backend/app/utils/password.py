"""
Password hashing utilities.

Note:
- We use pbkdf2_sha256 to avoid bcrypt's 72-byte password length limitation.
- pbkdf2_sha256 is a standard, strong password hashing algorithm without the
  bcrypt backend, so it supports long passwords safely.
"""
from passlib.context import CryptContext

# Use pbkdf2_sha256 to support long passwords safely
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    if password is None:
        password = ""

    # pbkdf2_sha256 does not have the 72-byte limit, so we can hash directly.
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)

