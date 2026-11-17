from typing import Optional, Any
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import APIKeyHeader
from app.config import settings
from app.services import user_service

# OpenAPI Security Schemes for Swagger /docs
secret_key_header_scheme = APIKeyHeader(
    name="X-Secret-Key",
    auto_error=False,
    description="System-wide SECRET_KEY (configured on Render)"
)

api_key_header_scheme = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="User / Platform API Key (generated in Users & API Keys portal)"
)

def authenticate_admin(username: str, password: str) -> bool:
    """Validate username and password against configured admin credentials."""
    if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD:
        return False
    return (
        username.strip() == settings.ADMIN_USERNAME
        and password.strip() == settings.ADMIN_PASSWORD
    )

def is_admin_authenticated(request: Request) -> bool:
    """Check if the current session belongs to an authenticated admin."""
    return bool(request.session.get("admin_logged_in", False))

def require_admin_portal(request: Request):
    """
    Dependency or helper to protect portal views.
    Redirects to /login if the admin session is not active.
    """
    if not is_admin_authenticated(request):
        return False
    return True

def extract_secret_key(request: Request, body_key: Optional[str] = None) -> Optional[str]:
    """Extract system SECRET_KEY from body, header, query, or Bearer auth."""
    if body_key:
        return str(body_key).strip()

    header_key = request.headers.get("x-secret-key")
    if header_key:
        return header_key.strip()

    query_key = request.query_params.get("secret_key")
    if query_key:
        return query_key.strip()

    # Authorization header fallback if matching SECRET_KEY
    auth_header = request.headers.get("authorization")
    if auth_header:
        parts = auth_header.strip().split()
        token = parts[1].strip() if len(parts) == 2 else parts[0].strip()
        if settings.SECRET_KEY and token == settings.SECRET_KEY.strip():
            return token

    return None

def extract_user_api_key(request: Request, body_key: Optional[str] = None) -> Optional[str]:
    """Extract User / Platform API Key from body, header, query, or Bearer auth."""
    if body_key:
        return str(body_key).strip()

    header_key = request.headers.get("x-api-key")
    if header_key:
        return header_key.strip()

    query_key = request.query_params.get("api_key")
    if query_key:
        return query_key.strip()

    # Authorization header fallback if not the SECRET_KEY
    auth_header = request.headers.get("authorization")
    if auth_header:
        parts = auth_header.strip().split()
        token = parts[1].strip() if len(parts) == 2 else parts[0].strip()
        if not (settings.SECRET_KEY and token == settings.SECRET_KEY.strip()):
            return token

    return None

def verify_customer_api_access(
    request: Request,
    body_secret_key: Optional[str] = None,
    body_api_key: Optional[str] = None,
) -> dict[str, Any]:
    """
    Both SECRET_KEY and User API Key are strictly required to manage customers via API.
    Portal admin session is permitted for web UI interaction.
    """
    if is_admin_authenticated(request):
        return {
            "type": "admin_session",
            "username": request.session.get("admin_user", "Admin"),
            "user": None,
        }

    # 1. Verify SECRET_KEY
    sk = extract_secret_key(request, body_secret_key)
    if not sk or not settings.SECRET_KEY or sk.strip() != settings.SECRET_KEY.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid SECRET_KEY is required. Provide via header 'X-Secret-Key', '?secret_key=' param, or body 'secret_key'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Verify User API Key
    ak = extract_user_api_key(request, body_api_key)
    if not ak:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid User API Key is required. Provide via header 'X-API-Key', '?api_key=' param, or body 'api_key'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = user_service.get_user_by_api_key(ak)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: The provided User API Key is invalid or has been deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"type": "user", "username": user.username, "user_id": user.id, "user": user}

def verify_admin_access(
    request: Request,
    sk_header: Optional[str] = Depends(secret_key_header_scheme),
) -> dict[str, Any]:
    """Verify Master Admin SECRET_KEY or Admin session."""
    if is_admin_authenticated(request):
        return {"type": "admin", "username": request.session.get("admin_user", "Admin"), "user": None}

    sk = extract_secret_key(request)
    if not sk or not settings.SECRET_KEY or sk.strip() != settings.SECRET_KEY.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Master SECRET_KEY is required for admin endpoints.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"type": "admin", "username": "Admin", "user": None}

# FastAPI Depends wrapper for dual-key requirement (SECRET_KEY + User API Key)
def verify_api_both_keys(
    request: Request,
    sk_header: Optional[str] = Depends(secret_key_header_scheme),
    ak_header: Optional[str] = Depends(api_key_header_scheme),
) -> dict[str, Any]:
    """FastAPI Depends wrapper for dual-key requirement (SECRET_KEY + User API Key)."""
    return verify_customer_api_access(request)
