from pydantic import BaseModel, EmailStr, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    phone: str
    password: str = Field(..., min_length=6, max_length=64)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    phone: str
    role: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)



class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str



class RefreshTokenRequest(BaseModel):
    refresh_token: str



class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    phone: Optional[str] = None


class UserChangePassword(BaseModel):
    old_password: str
    new_password: str