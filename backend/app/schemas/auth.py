from typing import Optional
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    organization_name: str
    subdomain: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str


class GoogleLoginRequest(BaseModel):
    id_token: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LoginResponse(BaseModel):
    otp_required: bool
    message: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    email: str
    
    class Config:
        from_attributes = True


class OrganizationResponse(BaseModel):
    id: int
    name: str
    subdomain: str
    
    class Config:
        from_attributes = True