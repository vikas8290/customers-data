from typing import Optional
from fastapi import Request, HTTPException, status
from app.config import settings

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

def validate_secret_key(key: Optional[str]) -> bool:
    """Check if provided key matches the configured SECRET_KEY."""
    if not settings.SECRET_KEY or not key:
        return False
    return key.strip() == settings.SECRET_KEY.strip()

def extract_secret_key_from_request(request: Request, body_key: Optional[str] = None) -> Optional[str]:
    """
    Extract secret key from:
    1. Body key (passed directly if sent in JSON or form)
    2. Header: X-Secret-Key or X-API-Key
    3. Header: Authorization (Bearer <SECRET_KEY>)
    4. Query parameter: ?secret_key=<SECRET_KEY> or ?api_key=<SECRET_KEY>
    """
    if body_key:
        return str(body_key).strip()

    # Headers
    header_key = request.headers.get("x-secret-key") or request.headers.get("x-api-key")
    if header_key:
        return header_key.strip()

    # Authorization header
    auth_header = request.headers.get("authorization")
    if auth_header:
        parts = auth_header.strip().split()
        if len(parts) == 2 and parts[0].lower() in ["bearer", "token", "apikey"]:
            return parts[1].strip()
        elif len(parts) == 1:
            return parts[0].strip()

    # Query params
    query_key = request.query_params.get("secret_key") or request.query_params.get("api_key")
    if query_key:
        return query_key.strip()

    return None

def verify_api_secret_key(request: Request, body_key: Optional[str] = None) -> bool:
    """
    Verify that the incoming request contains a valid SECRET_KEY.
    Allows active admin session or matching secret key.
    Raises 401 HTTPException if invalid or missing.
    """
    # 1. Allow active admin portal session
    if is_admin_authenticated(request):
        return True

    # 2. Extract key from body/header/query
    provided = extract_secret_key_from_request(request, body_key=body_key)

    if not validate_secret_key(provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid SECRET_KEY is required to access this API. Provide it via 'X-Secret-Key' header, 'Authorization: Bearer <SECRET_KEY>', '?secret_key=' query param, or in request body.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True
