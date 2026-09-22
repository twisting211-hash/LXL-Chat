import re
from fastapi import HTTPException, status

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,32}$")


def validate_username_str(username: str) -> str:
    cleaned = username.strip().lower()
    if not USERNAME_REGEX.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username must be 3-32 characters and contain only letters, numbers, and underscores.",
        )
    return cleaned


def validate_password_str(password: str) -> str:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters long.",
        )
    return password
