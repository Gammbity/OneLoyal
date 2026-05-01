from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.companies.schemas import CompanyResponse
from app.modules.users.schemas import UserResponse


class RegisterCompanyRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    company_slug: str = Field(min_length=2, max_length=120)
    owner_full_name: str = Field(min_length=1, max_length=255)
    owner_email: EmailStr
    owner_password: str = Field(min_length=8)

    @field_validator("company_slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.replace("-", "").isalnum():
            raise ValueError(
                "slug may contain only lowercase letters, numbers, and hyphens"
            )
        return normalized


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=16)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=16)


class AuthUserContext(BaseModel):
    user: UserResponse
    company: CompanyResponse | None

    model_config = ConfigDict(from_attributes=True)


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    company: CompanyResponse | None


class MeResponse(BaseModel):
    user: UserResponse
    company: CompanyResponse | None
    role: str
    company_id: UUID | None


class LogoutResponse(BaseModel):
    success: bool
