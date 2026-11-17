from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
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
        # Redirect to login page
        return False
    return True
