from typing import Optional, Any
from fastapi import Request, HTTPException, status
from app.config import settings
from app.services import user_service

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

def extract_api_key_from_request(request: Request, body_key: Optional[str] = None) -> Optional[str]:
    """
    Extract API key / Secret key from:
    1. Body key (passed directly if sent in JSON or form)
    2. Header: X-API-Key or X-Secret-Key
    3. Header: Authorization (Bearer <KEY>)
    4. Query parameter: ?api_key=<KEY> or ?secret_key=<KEY>
    """
    if body_key:
        return str(body_key).strip()

    # Headers
    header_key = request.headers.get("x-api-key") or request.headers.get("x-secret-key")
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
    query_key = request.query_params.get("api_key") or request.query_params.get("secret_key")
    if query_key:
        return query_key.strip()

    return None

def verify_api_access(request: Request, body_key: Optional[str] = None) -> dict[str, Any]:
    """
    Verify API access. Returns auth context dict:
    - {"type": "admin", "username": "admin"} if Master Secret Key or Admin session
    - {"type": "user", "username": user.username, "user_id": user.id, "user": user} if User API Key
    Raises 401 if key is missing or invalid.
    """
    # 1. Allow active admin portal session
    if is_admin_authenticated(request):
        return {"type": "admin", "username": request.session.get("admin_user", "admin"), "user": None}

    # 2. Extract key from body/header/query
    provided_key = extract_api_key_from_request(request, body_key=body_key)
    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid API Key or SECRET_KEY is required. Pass via header 'X-API-Key', 'Authorization: Bearer <KEY>', or query param '?api_key='.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check if it matches Master SECRET_KEY
    if settings.SECRET_KEY and provided_key.strip() == settings.SECRET_KEY.strip():
        return {"type": "admin", "username": "admin", "user": None}

    # 4. Check if it matches a registered user's API Key
    user = user_service.get_user_by_api_key(provided_key)
    if user:
        return {"type": "user", "username": user.username, "user_id": user.id, "user": user}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: The provided API Key is invalid or has been deactivated.",
        headers={"WWW-Authenticate": "Bearer"},
    )

def verify_api_secret_key(request: Request) -> dict[str, Any]:
    """FastAPI Depends wrapper for verify_api_access."""
    return verify_api_access(request)
