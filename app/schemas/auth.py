from pydantic import BaseModel, Field, field_validator
from app.schemas.user import UserPublic


class RegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=32,
        description="Username must be 3-32 characters, alphanumeric and underscores only."
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters long."
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean.replace("_", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, and underscores.")
        if len(clean) < 3 or len(clean) > 32:
            raise ValueError("Username must be between 3 and 32 characters.")
        return clean


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=1)

    @field_validator("username")
    @classmethod
    def clean_username(cls, v: str) -> str:
        return v.strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserPublic
