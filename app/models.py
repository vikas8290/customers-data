from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
import re

def normalize_indian_phone(phone_input: str) -> str:
    """
    Normalizes Indian phone numbers to strictly format: +91XXXXXXXXXX
    - 10 digits (e.g. 9876543210) -> +919876543210
    - 11 digits starting with 0 (e.g. 09876543210) -> +919876543210
    - 12 digits starting with 91 (e.g. 919876543210 or +919876543210) -> +919876543210
    - 13 digits starting with 091 (e.g. 0919876543210) -> +919876543210
    - Spaces, hyphens, parentheses, and dots are removed.
    Raises ValueError if the phone number cannot be resolved to a valid 10-digit Indian number.
    """
    if not phone_input or not str(phone_input).strip():
        raise ValueError("Phone number is required.")

    raw = str(phone_input).strip()
    cleaned = re.sub(r"[\s\-\(\)\.]", "", raw)
    digits = re.sub(r"\D", "", cleaned)

    if len(digits) == 10:
        return f"+91{digits}"
    elif len(digits) == 11 and digits.startswith("0"):
        return f"+91{digits[1:]}"
    elif len(digits) == 12 and digits.startswith("91"):
        return f"+91{digits[2:]}"
    elif len(digits) == 13 and digits.startswith("091"):
        return f"+91{digits[3:]}"
    else:
        raise ValueError(
            f"Invalid phone number '{raw}'. Indian phone numbers must be 10 digits (e.g. 9876543210) or in format +91XXXXXXXXXX (e.g. +919876543210)."
        )

class CustomerBase(BaseModel):
    # Only phone is required; all other fields are optional
    phone: str = Field(..., description="Customer Indian phone number (Stored as +91XXXXXXXXXX, Unique)")
    profile: Optional[str] = Field(default=None, description="Profile URL, image link, or bio")
    name: Optional[str] = Field(default=None, description="Customer full name")
    email: Optional[str] = Field(default=None, description="Customer email address")
    address: Optional[str] = Field(default=None, description="Detailed address")
    landmark: Optional[str] = Field(default=None, description="Nearby landmark")
    pincode: Optional[str] = Field(default=None, description="Postal / Zip code")
    city: Optional[str] = Field(default=None, description="City")
    state: Optional[str] = Field(default=None, description="State")
    from_source: Optional[str] = Field(
        default="Customer",
        alias="from",
        description="Source/Platform where data was collected. Shows user name if submitted via User API Key.",
    )
    data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Extra custom data stored as JSON (e.g. order details, tags, custom fields)",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore"
    )

    @field_validator("data", mode="before")
    @classmethod
    def parse_json_data(cls, v: Any) -> Optional[dict[str, Any]]:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            v_str = v.strip()
            if not v_str:
                return None
            try:
                import json
                parsed = json.loads(v_str)
                if isinstance(parsed, dict):
                    return parsed
                return {"value": parsed}
            except Exception:
                return {"info": v_str}
        return None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_indian_phone(v)

    @field_validator("profile", mode="before")
    @classmethod
    def clean_profile(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        v_str = str(v).strip()
        if not v_str or v_str.lower() in ("null", "none", "undefined", "n/a", "-", ""):
            return None
        return v_str

    @field_validator("name", "address", "landmark", "city", "state", "pincode", mode="before")
    @classmethod
    def clean_optional_strings(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        v_str = str(v).strip()
        if not v_str or v_str.lower() in ("null", "none", "undefined"):
            return None
        return v_str

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: Optional[str]) -> Optional[str]:
        if v:
            v = v.strip().lower()
            if not v or v in ("null", "none"):
                return None
            return v
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
    data: Optional[dict[str, Any]] = Field(default=None, description="Extra custom data stored as JSON")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore"
    )

    @field_validator("data", mode="before")
    @classmethod
    def parse_json_data(cls, v: Any) -> Optional[dict[str, Any]]:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            v_str = v.strip()
            if not v_str:
                return None
            try:
                import json
                parsed = json.loads(v_str)
                if isinstance(parsed, dict):
                    return parsed
                return {"value": parsed}
            except Exception:
                return {"info": v_str}
        return None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and str(v).strip():
            return normalize_indian_phone(v)
        return None

    @field_validator("profile", mode="before")
    @classmethod
    def clean_profile(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        v_str = str(v).strip()
        if not v_str or v_str.lower() in ("null", "none", "undefined", "n/a", "-", ""):
            return None
        return v_str

    @field_validator("name", "address", "landmark", "city", "state", "pincode", mode="before")
    @classmethod
    def clean_optional_strings(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        v_str = str(v).strip()
        if not v_str or v_str.lower() in ("null", "none", "undefined"):
            return None
        return v_str

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: Optional[str]) -> Optional[str]:
        if v:
            v = v.strip().lower()
            if not v or v in ("null", "none"):
                return None
            return v
        return None

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
    top_states: Optional[list[dict[str, Any]]] = Field(default_factory=list)
    chart_daily_labels: Optional[list[str]] = Field(default_factory=list)
    chart_daily_values: Optional[list[int]] = Field(default_factory=list)

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

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(extra="ignore")

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
