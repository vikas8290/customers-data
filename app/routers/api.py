from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, status, Query, Depends
from fastapi.responses import StreamingResponse
from app.models import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    PaginatedCustomersResponse,
    CustomerInDB,
    DashboardStats,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
)
from app.services import customer_service, user_service, excel_service
from app.database import db_manager
from app.auth import (
    verify_customer_api_access,
    verify_admin_access,
    verify_api_both_keys,
    secret_key_header_scheme,
    api_key_header_scheme,
)

router = APIRouter(prefix="/api", tags=["API Endpoints"])

@router.get("/health", summary="Service & Database Health Check")
def health_check():
    """Verify that the API and MongoDB connection are healthy (Public health check)."""
    is_db_connected = db_manager.ping()
    return {
        "status": "healthy" if is_db_connected else "degraded",
        "database_connected": is_db_connected,
        "timestamp": datetime.utcnow().isoformat(),
    }

@router.post(
    "/customers",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Collect Customer Data (Requires BOTH SECRET_KEY & User API Key)",
    description="Endpoint for platforms/websites to submit leads. Both SECRET_KEY and User API Key are strictly required. The customer's 'from' column is automatically tagged with the user/platform name."
)
async def collect_customer(
    request: Request,
    _sk: Optional[str] = Depends(secret_key_header_scheme),
    _ak: Optional[str] = Depends(api_key_header_scheme),
):
    """
    Accepts customer submission via JSON or Form Data.
    Requires BOTH valid SECRET_KEY and User API Key.
    Only `phone` is mandatory.
    """
    content_type = request.headers.get("content-type", "").lower()
    payload = {}
    
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON payload: {str(e)}"
            )
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        payload = dict(form)
    else:
        # Fallback attempt
        try:
            payload = await request.json()
        except Exception:
            form = await request.form()
            payload = dict(form)

    # 1. Extract API key and Secret key if provided inside the body
    body_secret_key = payload.pop("secret_key", None)
    body_api_key = payload.pop("api_key", None)

    # 2. Authenticate BOTH keys
    auth_ctx = verify_customer_api_access(
        request,
        body_secret_key=body_secret_key,
        body_api_key=body_api_key
    )

    # 3. Automatically assign the user's name to the "from" column
    if auth_ctx.get("type") == "user":
        payload["from_source"] = auth_ctx.get("username") or user_service.DEFAULT_CUSTOMER_USERNAME
    else:
        source = payload.get("from_source") or payload.get("from")
        if not source or str(source).strip().lower() in ["website", "portal", "none", ""]:
            source = user_service.DEFAULT_CUSTOMER_USERNAME
        payload["from_source"] = source

    try:
        data = CustomerCreate(**payload)
    except Exception as e:
        status_code = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        raise HTTPException(
            status_code=status_code,
            detail=f"Validation error: {str(e)}"
        )

    # Capture client IP and User-Agent for audit
    client_ip = request.client.host if request.client else None
    if "x-forwarded-for" in request.headers:
        client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
    user_agent = request.headers.get("user-agent")

    try:
        created = customer_service.create_customer(
            data=data,
            ip_address=client_ip,
            user_agent=user_agent
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ve)
        )
    except Exception as e:
        err_msg = str(e)
        if "duplicate key" in err_msg.lower() or "e11000" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Customer with phone number '{data.phone}' already exists."
            )
        if "SSL handshake failed" in err_msg or "ServerSelectionTimeoutError" in err_msg or "TLSV1_ALERT" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed: MongoDB Atlas IP whitelist blocking Render. Please allow 0.0.0.0/0 in MongoDB Atlas Network Access."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err_msg}"
        )

    return CustomerResponse(
        success=True,
        message="Customer data recorded successfully.",
        data=created
    )

@router.get(
    "/customers",
    response_model=PaginatedCustomersResponse,
    dependencies=[Depends(verify_api_both_keys)],
    summary="Get List of Customers (Requires BOTH SECRET_KEY & User API Key)"
)
def get_customers(
    search: Optional[str] = Query(None, description="Search term for name, phone, email, city, address"),
    source: Optional[str] = Query(None, alias="from", description="Filter by platform / user name (e.g., Shopify, Website-1)"),
    city: Optional[str] = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Retrieve filtered, paginated customers list."""
    items, total = customer_service.list_customers(
        search=search,
        source=source,
        city=city,
        state=state,
        page=page,
        page_size=page_size
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return PaginatedCustomersResponse(
        success=True,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items
    )

@router.get(
    "/customers/export/excel",
    dependencies=[Depends(verify_api_both_keys)],
    summary="Download Filtered Customers in Excel File (Requires BOTH SECRET_KEY & User API Key)",
    description="Export customer records to an Excel (.xlsx) spreadsheet matching search, source, city, and state filters."
)
def api_export_customers_excel(
    search: Optional[str] = Query(None, description="Search term across name, phone, email, city, address"),
    source: Optional[str] = Query(None, alias="from", description="Filter by platform / user source"),
    city: Optional[str] = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state"),
):
    """Generates and streams an Excel spreadsheet of filtered customers."""
    customers = customer_service.get_all_customers_for_export(
        search=search,
        source=source,
        city=city,
        state=state,
    )
    buffer = excel_service.generate_customers_excel(customers)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"customers_export_{timestamp}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@router.get(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(verify_api_both_keys)],
    summary="Get Single Customer by ID (Requires BOTH SECRET_KEY & User API Key)"
)
def get_customer(customer_id: str):
    """Fetch details of a specific customer by ID."""
    customer = customer_service.get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found."
        )
    return CustomerResponse(success=True, message="Customer found", data=customer)

@router.put(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(verify_api_both_keys)],
    summary="Update Customer Details (Requires BOTH SECRET_KEY & User API Key)"
)
def update_customer(customer_id: str, data: CustomerUpdate):
    """Update details of an existing customer."""
    try:
        updated = customer_service.update_customer(customer_id, data)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ve)
        )
    except Exception as e:
        err_msg = str(e)
        if "duplicate key" in err_msg.lower() or "e11000" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another customer with phone number '{data.phone}' already exists."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {err_msg}"
        )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found or could not be updated."
        )
    return CustomerResponse(
        success=True,
        message="Customer updated successfully.",
        data=updated
    )

@router.delete(
    "/customers/{customer_id}",
    dependencies=[Depends(verify_api_both_keys)],
    summary="Delete Customer Record (Requires BOTH SECRET_KEY & User API Key)"
)
def delete_customer(customer_id: str):
    """Delete a customer record by ID."""
    success = customer_service.delete_customer(customer_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found."
        )
    return {"success": True, "message": "Customer record deleted successfully."}

@router.get(
    "/stats",
    response_model=DashboardStats,
    dependencies=[Depends(verify_api_both_keys)],
    summary="Customer Analytics & Statistics (Requires BOTH SECRET_KEY & User API Key)"
)
def get_stats():
    """Retrieve summary metrics, source distribution, and city counts."""
    stats = customer_service.get_dashboard_stats()
    return DashboardStats(**stats)

@router.get(
    "/sources",
    dependencies=[Depends(verify_api_secret_key := verify_api_both_keys)],
    summary="List Distinct Platform / User Sources (Requires BOTH SECRET_KEY & User API Key)"
)
def get_sources():
    """Returns a list of all platforms/sources recorded across customers."""
    sources = customer_service.get_unique_sources()
    return {"success": True, "sources": sources}

# ================= ADMIN USER & API KEY MANAGEMENT ENDPOINTS =================

@router.post(
    "/admin/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: Register Platform User & Generate Key (Requires SECRET_KEY)"
)
def api_create_user(data: UserCreate, auth: dict = Depends(verify_admin_access)):
    """Admin registers a user/platform and automatically generates their API key."""
    try:
        user = user_service.create_user(data)
        return UserResponse(success=True, message="User registered successfully", data=user)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.get(
    "/admin/users",
    response_model=UserListResponse,
    summary="Admin: List All Registered Users & API Keys (Requires SECRET_KEY)"
)
def api_list_users(auth: dict = Depends(verify_admin_access)):
    """List all registered users, their API keys, and collected lead counts."""
    users = user_service.list_users()
    return UserListResponse(success=True, total=len(users), users=users)

@router.put(
    "/admin/users/{user_id}",
    response_model=UserResponse,
    summary="Admin: Update User / Platform Details (Requires SECRET_KEY)"
)
def api_update_user(user_id: str, data: UserUpdate, auth: dict = Depends(verify_admin_access)):
    """Admin updates platform username, email, notes, or active status."""
    try:
        user = user_service.update_user(
            user_id=user_id,
            username=data.username,
            email=data.email,
            notes=data.notes,
            is_active=data.is_active,
        )
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return UserResponse(success=True, message="User updated successfully", data=user)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@router.delete(
    "/admin/users/{user_id}",
    summary="Admin: Delete User & Revoke Key (Requires SECRET_KEY)"
)
def api_delete_user(user_id: str, auth: dict = Depends(verify_admin_access)):
    """Delete a user/platform and revoke their API key."""
    success = user_service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return {"success": True, "message": "User deleted and API key revoked."}
