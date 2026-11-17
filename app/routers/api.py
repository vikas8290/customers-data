from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, status, Query
from app.models import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    PaginatedCustomersResponse,
    CustomerInDB,
    DashboardStats,
)
from app.services import customer_service
from app.database import db_manager

router = APIRouter(prefix="/api", tags=["API Endpoints"])

@router.get("/health", summary="Service & Database Health Check")
def health_check():
    """Verify that the API and MongoDB connection are healthy."""
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
    summary="Collect Customer Data (Public API for Websites / Forms)",
    description="Endpoint for websites, landing pages, or external systems to submit customer data. Only 'phone' is required; all other fields are optional."
)
async def collect_customer(request: Request):
    """
    Accepts customer submission via JSON or Form Data.
    Only `phone` is mandatory.
    Fields supported:
    - phone (Required)
    - profile (Optional)
    - name (Optional)
    - email (Optional)
    - address (Optional)
    - landmark (Optional)
    - pincode (Optional)
    - city (Optional)
    - state (Optional)
    - from (Optional, e.g. 'website', 'contact-form', 'landing-page')
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

    # Allow 'source' or 'from' in payload
    if "from" in payload and "from_source" not in payload:
        payload["from_source"] = payload["from"]

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
    except Exception as e:
        err_msg = str(e)
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
    summary="Get List of Customers with Pagination & Filtering"
)
def get_customers(
    search: Optional[str] = Query(None, description="Search term for name, phone, email, city, address"),
    source: Optional[str] = Query(None, alias="from", description="Filter by collection source (e.g., website)"),
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
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    summary="Get Single Customer by ID"
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
    summary="Update Customer Details"
)
def update_customer(customer_id: str, data: CustomerUpdate):
    """Update details of an existing customer."""
    updated = customer_service.update_customer(customer_id, data)
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
    summary="Delete Customer Record"
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
    summary="Customer Analytics & Statistics"
)
def get_stats():
    """Retrieve summary metrics, source distribution, and city counts."""
    stats = customer_service.get_dashboard_stats()
    return DashboardStats(**stats)

@router.get(
    "/sources",
    summary="List Distinct Collection Sources"
)
def get_sources():
    """Returns a list of all sources recorded across customers."""
    sources = customer_service.get_unique_sources()
    return {"success": True, "sources": sources}
