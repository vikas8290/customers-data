from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
import re

class CustomerBase(BaseModel):
    # Only phone is required; all other fields are optional
    phone: str = Field(..., description="Customer phone number (Required)")
    profile: Optional[str] = Field(default=None, description="Profile URL, image link, or bio")
    name: Optional[str] = Field(default=None, description="Customer full name")
    email: Optional[str] = Field(default=None, description="Customer email address")
    address: Optional[str] = Field(default=None, description="Detailed address")
    landmark: Optional[str] = Field(default=None, description="Nearby landmark")
    pincode: Optional[str] = Field(default=None, description="Postal / Zip code")
    city: Optional[str] = Field(default=None, description="City")
    state: Optional[str] = Field(default=None, description="State")
    from_source: Optional[str] = Field(
        default="website",
        alias="from",
        description="Source/Platform where data was collected. Shows user name if submitted via User API Key.",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore"
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Phone number cannot be empty.")
        digits_only = re.sub(r"[^\d+]", "", cleaned)
        if len(digits_only) < 5:
            raise ValueError("Phone number must contain at least 5 digits.")
        return cleaned

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: Optional[str]) -> Optional[str]:
        if v:
            v = v.strip().lower()
            return v if v else None
        return None

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    phone: Optional[str] = None
    profile: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    landmark: Optional[str] = None
    pincode: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    from_source: Optional[str] = Field(default=None, alias="from")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore"
    )

class CustomerInDB(CustomerBase):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

class CustomerResponse(BaseModel):
    success: bool = True
    message: str = "Success"
    data: Optional[CustomerInDB] = None

class PaginatedCustomersResponse(BaseModel):
    success: bool = True
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[CustomerInDB]

class DashboardStats(BaseModel):
    total_customers: int
    today_count: int
    this_week_count: int
    this_month_count: int
    sources_breakdown: dict[str, int]
    top_cities: list[dict[str, Any]]

# ================= USER / API KEY MODELS =================

class UserCreate(BaseModel):
    username: str = Field(..., description="Platform / User name (e.g. Shopify, Website-1, MobileApp, Rahul)")
    email: Optional[str] = Field(default=None, description="Optional contact email")
    notes: Optional[str] = Field(default=None, description="Optional platform notes or description")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("User/Platform name cannot be empty.")
        return cleaned

class UserInDB(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    notes: Optional[str] = None
    api_key: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: Optional[datetime] = None
    leads_count: int = 0

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

class UserResponse(BaseModel):
    success: bool = True
    message: str = "Success"
    data: Optional[UserInDB] = None

class UserListResponse(BaseModel):
    success: bool = True
    total: int
    users: list[UserInDB]
