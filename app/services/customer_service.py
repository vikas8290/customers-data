from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from bson import ObjectId
from pymongo import DESCENDING
from app.database import get_customers_collection
from app.models import CustomerCreate, CustomerUpdate, CustomerInDB

def doc_to_customer(doc: dict[str, Any]) -> CustomerInDB:
    """Helper to convert MongoDB document to CustomerInDB model."""
    doc_copy = dict(doc)
    doc_copy["id"] = str(doc_copy.pop("_id"))
    # Map stored 'from' to 'from_source' or alias
    if "from" in doc_copy:
        doc_copy["from_source"] = doc_copy.get("from")
    return CustomerInDB(**doc_copy)

def create_customer(
    data: CustomerCreate,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> CustomerInDB:
    """Insert a new customer document into MongoDB."""
    col = get_customers_collection()
    now = datetime.now(timezone.utc)
    
    doc = {
        "phone": data.phone.strip(),
        "profile": data.profile.strip() if data.profile else None,
        "name": data.name.strip() if data.name else None,
        "email": data.email.strip().lower() if data.email else None,
        "address": data.address.strip() if data.address else None,
        "landmark": data.landmark.strip() if data.landmark else None,
        "pincode": data.pincode.strip() if data.pincode else None,
        "city": data.city.strip() if data.city else None,
        "state": data.state.strip() if data.state else None,
        "from": (data.from_source.strip() if data.from_source else "website"),
        "created_at": now,
        "updated_at": now,
        "meta": {
            "ip": ip_address,
            "user_agent": user_agent,
        }
    }
    
    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc_to_customer(doc)

def get_customer_by_id(customer_id: str) -> Optional[CustomerInDB]:
    """Retrieve customer by MongoDB ObjectId."""
    try:
        obj_id = ObjectId(customer_id)
    except Exception:
        return None
    col = get_customers_collection()
    doc = col.find_one({"_id": obj_id})
    return doc_to_customer(doc) if doc else None

def get_customer_by_phone(phone: str) -> Optional[CustomerInDB]:
    """Retrieve the most recent customer entry by phone number."""
    col = get_customers_collection()
    doc = col.find_one({"phone": phone.strip()}, sort=[("created_at", DESCENDING)])
    return doc_to_customer(doc) if doc else None

def update_customer(customer_id: str, data: CustomerUpdate) -> Optional[CustomerInDB]:
    """Update existing customer by ObjectId."""
    try:
        obj_id = ObjectId(customer_id)
    except Exception:
        return None
    
    update_data = {}
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "from_source":
            update_data["from"] = value
        elif value is not None:
            update_data[key] = value.strip() if isinstance(value, str) else value
            
    if not update_data:
        return get_customer_by_id(customer_id)
        
    update_data["updated_at"] = datetime.now(timezone.utc)
    col = get_customers_collection()
    result = col.find_one_and_update(
        {"_id": obj_id},
        {"$set": update_data},
        return_document=True
    )
    return doc_to_customer(result) if result else None

def delete_customer(customer_id: str) -> bool:
    """Delete a customer by ObjectId."""
    try:
        obj_id = ObjectId(customer_id)
    except Exception:
        return False
    col = get_customers_collection()
    res = col.delete_one({"_id": obj_id})
    return res.deleted_count > 0

def build_query_filter(
    search: Optional[str] = None,
    source: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict[str, Any]:
    """Build a MongoDB filter dict based on search and filter options."""
    query: dict[str, Any] = {}
    
    if search:
        search_regex = {"$regex": search.strip(), "$options": "i"}
        query["$or"] = [
            {"phone": search_regex},
            {"name": search_regex},
            {"email": search_regex},
            {"city": search_regex},
            {"state": search_regex},
            {"address": search_regex},
            {"from": search_regex},
        ]
        
    if source:
        query["from"] = {"$regex": f"^{source.strip()}$", "$options": "i"}
        
    if city:
        query["city"] = {"$regex": f"^{city.strip()}$", "$options": "i"}
        
    if state:
        query["state"] = {"$regex": f"^{state.strip()}$", "$options": "i"}
        
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        query["created_at"] = date_filter
        
    return query

def list_customers(
    search: Optional[str] = None,
    source: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[CustomerInDB], int]:
    """List paginated customers with optional filters."""
    col = get_customers_collection()
    query = build_query_filter(search, source, city, state, start_date, end_date)
    
    total = col.count_documents(query)
    
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    skip = (page - 1) * page_size
    
    cursor = col.find(query).sort("created_at", DESCENDING).skip(skip).limit(page_size)
    items = [doc_to_customer(doc) for doc in cursor]
    
    return items, total

def get_all_customers_for_export(
    search: Optional[str] = None,
    source: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50000,
) -> list[CustomerInDB]:
    """Retrieve all matching customers for Excel export."""
    col = get_customers_collection()
    query = build_query_filter(search, source, city, state, start_date, end_date)
    cursor = col.find(query).sort("created_at", DESCENDING).limit(limit)
    return [doc_to_customer(doc) for doc in cursor]

def get_unique_sources() -> list[str]:
    """Get list of distinct source names."""
    col = get_customers_collection()
    sources = col.distinct("from")
    return [s for s in sources if s]

def get_dashboard_stats() -> dict[str, Any]:
    """Compute dashboard analytics and metrics."""
    col = get_customers_collection()
    now = datetime.now(timezone.utc)
    
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    
    total = col.count_documents({})
    today_count = col.count_documents({"created_at": {"$gte": today_start}})
    week_count = col.count_documents({"created_at": {"$gte": week_start}})
    month_count = col.count_documents({"created_at": {"$gte": month_start}})
    
    # Sources breakdown
    sources_pipeline = [
        {"$group": {"_id": {"$ifNull": ["$from", "website"]}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    sources_breakdown = {
        item["_id"]: item["count"] for item in col.aggregate(sources_pipeline)
    }
    
    # Top cities
    cities_pipeline = [
        {"$match": {"city": {"$ne": None, "$ne": ""}}},
        {"$group": {"_id": "$city", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    top_cities = [
        {"city": item["_id"], "count": item["count"]}
        for item in col.aggregate(cities_pipeline)
    ]
    
    return {
        "total_customers": total,
        "today_count": today_count,
        "this_week_count": week_count,
        "this_month_count": month_count,
        "sources_breakdown": sources_breakdown,
        "top_cities": top_cities,
    }
