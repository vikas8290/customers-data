from typing import Optional
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.auth import authenticate_admin, is_admin_authenticated
from app.services import customer_service, excel_service, user_service
from app.models import CustomerCreate, CustomerUpdate, UserCreate

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def format_kolkata_time(dt: Optional[datetime]) -> str:
    """Format datetime in Asia/Kolkata timezone (UTC+05:30) with 12-hour AM/PM format."""
    if not dt:
        return "-"
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        kolkata_tz = timezone(timedelta(hours=5, minutes=30))
        dt_kolkata = dt.astimezone(kolkata_tz)
        return dt_kolkata.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return str(dt)

templates.env.filters["to_kolkata"] = format_kolkata_time

router = APIRouter(tags=["Admin Portal"])

@router.get("/", include_in_schema=False)
def root(request: Request):
    """Root redirect to dashboard if logged in, else to login page."""
    if is_admin_authenticated(request):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request, error: Optional[str] = None):
    """Render Admin Login page."""
    if is_admin_authenticated(request):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error}
    )

@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
def handle_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Process admin credentials and establish session."""
    if authenticate_admin(username, password):
        request.session["admin_logged_in"] = True
        request.session["admin_user"] = username
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": "Invalid username or password. Please try again.",
            "username": username,
        },
        status_code=status.HTTP_401_UNAUTHORIZED
    )

@router.get("/logout", include_in_schema=False)
def logout(request: Request):
    """Clear session and log out."""
    request.session.clear()
    return RedirectResponse(url="/login?msg=logged_out", status_code=status.HTTP_302_FOUND)

@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard(
    request: Request,
    search: Optional[str] = None,
    source: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    new_user: Optional[str] = None,
    new_key: Optional[str] = None,
):
    """Render the customer management dashboard with search, filters, metrics, and user management."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    db_error = error
    items, total = [], 0
    stats = {
        "total_customers": 0,
        "today_count": 0,
        "this_week_count": 0,
        "this_month_count": 0,
        "sources_breakdown": {},
        "top_cities": [],
        "top_states": [],
        "chart_daily_labels": [],
        "chart_daily_values": [],
    }
    unique_sources = []
    unique_cities = []
    unique_states = []
    users = []

    try:
        items, total = customer_service.list_customers(
            search=search,
            source=source,
            city=city,
            state=state,
            page=page,
            page_size=page_size,
        )
        stats = customer_service.get_dashboard_stats()
        unique_sources = customer_service.get_unique_sources()
        unique_cities = customer_service.get_unique_cities()
        unique_states = customer_service.get_unique_states()
        users = user_service.list_users()
    except Exception as e:
        err_msg = str(e)
        if "SSL handshake failed" in err_msg or "ServerSelectionTimeoutError" in err_msg or "TLSV1_ALERT" in err_msg:
            db_error = (
                "MongoDB Atlas Connection Blocked: Your MongoDB Atlas cluster is not allowing connections from Render's IP address. "
                "Please go to MongoDB Atlas Dashboard -> Network Access -> Add IP Address -> Select 'Allow Access from Anywhere' (0.0.0.0/0)."
            )
        else:
            db_error = f"Database error: {err_msg}"

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    # Generate pagination window
    if total_pages <= 7:
        pagination_pages = list(range(1, total_pages + 1))
    else:
        if page <= 4:
            pagination_pages = [1, 2, 3, 4, 5, "...", total_pages]
        elif page >= total_pages - 3:
            pagination_pages = [1, "...", total_pages - 4, total_pages - 3, total_pages - 2, total_pages - 1, total_pages]
        else:
            pagination_pages = [1, "...", page - 1, page, page + 1, "...", total_pages]

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": request.session.get("admin_user", "Admin"),
            "customers": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "pagination_pages": pagination_pages,
            "stats": stats,
            "unique_sources": unique_sources,
            "unique_cities": unique_cities,
            "unique_states": unique_states,
            "users": users,
            "search": search or "",
            "source_filter": source or "",
            "city_filter": city or "",
            "state_filter": state or "",
            "msg": msg,
            "error": db_error,
            "new_user": new_user,
            "new_key": new_key,
        }
    )

@router.get("/customers", response_class=HTMLResponse, include_in_schema=False)
def customers_page(
    request: Request,
    search: Optional[str] = None,
    source: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    new_user: Optional[str] = None,
    new_key: Optional[str] = None,
):
    """Dedicated Customer Management Page with full table and searchable filter dropdowns."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    items = []
    total = 0
    unique_sources = []
    unique_cities = []
    unique_states = []
    db_error = error

    try:
        items, total = customer_service.list_customers(
            search=search,
            source=source,
            city=city,
            state=state,
            page=page,
            page_size=page_size,
        )
        unique_sources = customer_service.get_unique_sources()
        unique_cities = customer_service.get_unique_cities()
        unique_states = customer_service.get_unique_states()
    except Exception as e:
        err_msg = str(e)
        if "SSL handshake failed" in err_msg or "ServerSelectionTimeoutError" in err_msg or "TLSV1_ALERT" in err_msg:
            db_error = (
                "MongoDB Atlas Connection Blocked: Your MongoDB Atlas cluster is not allowing connections from Render's IP address. "
                "Please go to MongoDB Atlas Dashboard -> Network Access -> Add IP Address -> Select 'Allow Access from Anywhere' (0.0.0.0/0)."
            )
        else:
            db_error = f"Database error: {err_msg}"

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    # Generate pagination window
    if total_pages <= 7:
        pagination_pages = list(range(1, total_pages + 1))
    else:
        if page <= 4:
            pagination_pages = [1, 2, 3, 4, 5, "...", total_pages]
        elif page >= total_pages - 3:
            pagination_pages = [1, "...", total_pages - 4, total_pages - 3, total_pages - 2, total_pages - 1, total_pages]
        else:
            pagination_pages = [1, "...", page - 1, page, page + 1, "...", total_pages]

    return templates.TemplateResponse(
        request=request,
        name="customers.html",
        context={
            "user": request.session.get("admin_user", "Admin"),
            "customers": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "pagination_pages": pagination_pages,
            "unique_sources": unique_sources,
            "unique_cities": unique_cities,
            "unique_states": unique_states,
            "search": search or "",
            "source_filter": source or "",
            "city_filter": city or "",
            "state_filter": state or "",
            "msg": msg,
            "error": db_error,
            "new_user": new_user,
            "new_key": new_key,
        }
    )

@router.post("/portal/customer/add", include_in_schema=False)
def portal_add_customer(
    request: Request,
    phone: str = Form(...),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    profile: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    landmark: Optional[str] = Form(None),
    pincode: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    from_source: Optional[str] = Form(None),
    data: Optional[str] = Form(None),
    redirect_to: Optional[str] = Form("/customers"),
):
    """Add a customer directly through the admin portal."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    dest = redirect_to or "/customers"
    sep = "&" if "?" in dest else "?"
    try:
        source = from_source.strip() if from_source and from_source.strip() else user_service.DEFAULT_CUSTOMER_USERNAME
        if source.lower() in ["website", "portal", "none", ""]:
            source = user_service.DEFAULT_CUSTOMER_USERNAME

        cust_create = CustomerCreate(
            phone=phone,
            name=name or None,
            email=email or None,
            profile=profile or None,
            address=address or None,
            landmark=landmark or None,
            pincode=pincode or None,
            city=city or None,
            state=state or None,
            from_source=source,
            data=data or None,
        )
        customer_service.create_customer(cust_create, ip_address="admin-portal")
        return RedirectResponse(url=f"{dest}{sep}msg=added", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        err_text = quote_plus(str(e))
        return RedirectResponse(url=f"{dest}{sep}error={err_text}", status_code=status.HTTP_302_FOUND)

@router.post("/portal/customer/{customer_id}/edit", include_in_schema=False)
def portal_edit_customer(
    request: Request,
    customer_id: str,
    phone: str = Form(...),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    profile: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    landmark: Optional[str] = Form(None),
    pincode: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    from_source: Optional[str] = Form(None),
    data: Optional[str] = Form(None),
    redirect_to: Optional[str] = Form("/customers"),
):
    """Edit customer details from the portal."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    dest = redirect_to or "/customers"
    sep = "&" if "?" in dest else "?"
    try:
        cust_update = CustomerUpdate(
            phone=phone,
            name=name,
            email=email,
            profile=profile,
            address=address,
            landmark=landmark,
            pincode=pincode,
            city=city,
            state=state,
            from_source=from_source,
            data=data,
        )
        customer_service.update_customer(customer_id, cust_update)
        return RedirectResponse(url=f"{dest}{sep}msg=updated", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        err_text = quote_plus(str(e))
        return RedirectResponse(url=f"{dest}{sep}error={err_text}", status_code=status.HTTP_302_FOUND)

@router.post("/portal/customer/{customer_id}/delete", include_in_schema=False)
def portal_delete_customer(
    request: Request,
    customer_id: str,
    redirect_to: Optional[str] = Form("/customers"),
):
    """Delete customer record from the portal."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    dest = redirect_to or "/customers"
    sep = "&" if "?" in dest else "?"
    customer_service.delete_customer(customer_id)
    return RedirectResponse(url=f"{dest}{sep}msg=deleted", status_code=status.HTTP_302_FOUND)

# ================= ADMIN USER / PLATFORM REGISTRATION ROUTES =================

@router.get("/users", response_class=HTMLResponse, include_in_schema=False)
def users_page(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    new_user: Optional[str] = None,
    new_key: Optional[str] = None,
):
    """Render the dedicated Platform Users & API Keys management page."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    users = []
    db_error = error
    try:
        users = user_service.list_users()
    except Exception as e:
        db_error = f"Database error fetching users: {str(e)}"

    total_leads = sum(u.leads_count for u in users)

    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "user": request.session.get("admin_user", "Admin"),
            "users": users,
            "total_users": len(users),
            "total_leads": total_leads,
            "msg": msg,
            "error": db_error,
            "new_user": new_user,
            "new_key": new_key,
        }
    )

@router.post("/portal/user/add", include_in_schema=False)
def portal_add_user(
    request: Request,
    username: str = Form(...),
    email: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    redirect_to: Optional[str] = Form("/users"),
):
    """Admin registers a user/platform and generates their API Key."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    dest = redirect_to or "/users"
    sep = "&" if "?" in dest else "?"
    try:
        data = UserCreate(username=username, email=email or None, notes=notes or None)
        new_user = user_service.create_user(data)
        return RedirectResponse(
            url=f"{dest}{sep}msg=user_added&new_user={new_user.username}&new_key={new_user.api_key}",
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        return RedirectResponse(url=f"{dest}{sep}error={str(e)}", status_code=status.HTTP_302_FOUND)

@router.post("/portal/user/{user_id}/delete", include_in_schema=False)
def portal_delete_user(request: Request, user_id: str, redirect_to: Optional[str] = Form("/users")):
    """Admin deletes user and revokes their API Key."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    dest = redirect_to or "/users"
    sep = "&" if "?" in dest else "?"
    user_service.delete_user(user_id)
    return RedirectResponse(url=f"{dest}{sep}msg=user_deleted", status_code=status.HTTP_302_FOUND)

@router.post("/portal/user/{user_id}/regenerate-key", include_in_schema=False)
def portal_regenerate_user_key(request: Request, user_id: str, redirect_to: Optional[str] = Form("/users")):
    """Admin regenerates a new API Key for a user."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    dest = redirect_to or "/users"
    sep = "&" if "?" in dest else "?"
    new_key = user_service.regenerate_api_key(user_id)
    return RedirectResponse(url=f"{dest}{sep}msg=key_regenerated&new_key={new_key}", status_code=status.HTTP_302_FOUND)

@router.post("/portal/user/{user_id}/edit", include_in_schema=False)
def portal_edit_user(
    request: Request,
    user_id: str,
    username: str = Form(...),
    email: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(True),
    redirect_to: Optional[str] = Form("/users"),
):
    """Admin updates user/platform details."""
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    dest = redirect_to or "/users"
    sep = "&" if "?" in dest else "?"
    try:
        user_service.update_user(
            user_id=user_id,
            username=username,
            email=email,
            notes=notes,
            is_active=is_active,
        )
        return RedirectResponse(url=f"{dest}{sep}msg=user_updated", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        err_text = quote_plus(str(e))
        return RedirectResponse(url=f"{dest}{sep}error={err_text}", status_code=status.HTTP_302_FOUND)

@router.get("/export/excel", summary="Export Customers to Excel Spreadsheet")
def export_excel(
    request: Request,
    search: Optional[str] = None,
    source: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
):
    """
    Download an Excel file (.xlsx) containing all or filtered customer records.
    Accessible from the portal or directly with admin session.
    """
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    customers = customer_service.get_all_customers_for_export(
        search=search,
        source=source,
        city=city,
        state=state,
    )

    buffer = excel_service.generate_customers_excel(customers)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"customers_data_export_{timestamp}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
