from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from bson import ObjectId
from pymongo import DESCENDING
from app.database import get_customers_collection, get_users_collection
from app.models import (
    CustomerCreate,
    CustomerUpdate,
    CustomerInDB,
    normalize_text_lower,
    normalize_city,
    normalize_state,
    normalize_pincode,
    normalize_profile,
    NULL_EQUIVALENTS,
)

INVALID_LOCATION_VALS = {"", "none", "null", "nil", "na", "n/a", "-", "--", "undefined"}

def doc_to_customer(doc: dict[str, Any]) -> CustomerInDB:
    """Helper to convert MongoDB document to CustomerInDB model with clean lowercase text."""
    doc_copy = dict(doc)
    doc_copy["id"] = str(doc_copy.pop("_id"))
    from_val = doc_copy.get("from")
    if not from_val or from_val in ("website", "portal", "None", "", None):
        from_val = "Customer"
    doc_copy["from"] = from_val
    doc_copy["from_source"] = from_val

    # Normalize fields to lowercase and clean null equivalents
    doc_copy["profile"] = normalize_profile(doc_copy.get("profile"))
    doc_copy["name"] = normalize_text_lower(doc_copy.get("name"))
    doc_copy["email"] = normalize_text_lower(doc_copy.get("email"))
    doc_copy["address"] = normalize_text_lower(doc_copy.get("address"))
    doc_copy["landmark"] = normalize_text_lower(doc_copy.get("landmark"))
    doc_copy["pincode"] = normalize_pincode(doc_copy.get("pincode"))
    doc_copy["city"] = normalize_city(doc_copy.get("city"))
    doc_copy["state"] = normalize_state(doc_copy.get("state"))

    return CustomerInDB(**doc_copy)

def create_customer(
    data: CustomerCreate,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> CustomerInDB:
    """Insert a new customer document into MongoDB with unique phone enforcement."""
    col = get_customers_collection()
    phone = data.phone.strip()

    # Enforce uniqueness
    existing = col.find_one({"phone": phone})
    if existing:
        raise ValueError(f"Customer with phone number '{phone}' already exists.")

    from_source = data.from_source.strip() if data.from_source and data.from_source.strip() else "Customer"
    if from_source.lower() in ("website", "portal", "none", ""):
        from_source = "Customer"

    now = datetime.now(timezone.utc)
    doc = {
        "phone": phone,
        "profile": normalize_profile(data.profile),
        "name": normalize_text_lower(data.name),
        "email": normalize_text_lower(data.email),
        "address": normalize_text_lower(data.address),
        "landmark": normalize_text_lower(data.landmark),
        "pincode": normalize_pincode(data.pincode),
        "city": normalize_city(data.city),
        "state": normalize_state(data.state),
        "from": from_source,
        "data": data.data if data.data else None,
        "created_at": now,
        "updated_at": now,
        "meta": {
            "ip": ip_address,
            "user_agent": user_agent,
        }
    }
    
    try:
        result = col.insert_one(doc)
    except Exception as e:
        if "duplicate key" in str(e).lower() or "e11000" in str(e).lower():
            raise ValueError(f"Customer with phone number '{phone}' already exists.")
        raise

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
    """Retrieve the customer entry by normalized phone number."""
    col = get_customers_collection()
    doc = col.find_one({"phone": phone.strip()})
    return doc_to_customer(doc) if doc else None

def update_customer(customer_id: str, data: CustomerUpdate) -> Optional[CustomerInDB]:
    """Update existing customer by ObjectId with unique phone enforcement."""
    try:
        obj_id = ObjectId(customer_id)
    except Exception:
        return None
    
    col = get_customers_collection()
    update_data = {}
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "from_source":
            update_data["from"] = value
        elif key in ("name", "email", "address", "landmark"):
            update_data[key] = normalize_text_lower(value)
        elif key == "city":
            update_data["city"] = normalize_city(value)
        elif key == "state":
            update_data["state"] = normalize_state(value)
        elif key == "pincode":
            update_data["pincode"] = normalize_pincode(value)
        elif key == "profile":
            update_data["profile"] = normalize_profile(value)
        elif isinstance(value, str):
            val_clean = value.strip().lower()
            update_data[key] = val_clean if val_clean not in NULL_EQUIVALENTS else None
        else:
            update_data[key] = value
            
    if not update_data:
        return get_customer_by_id(customer_id)
    
    # If phone is updated, ensure no duplicate exists on another record
    if "phone" in update_data:
        new_phone = update_data["phone"]
        existing = col.find_one({"phone": new_phone, "_id": {"$ne": obj_id}})
        if existing:
            raise ValueError(f"Another customer with phone number '{new_phone}' already exists.")
        
    update_data["updated_at"] = datetime.now(timezone.utc)
    try:
        result = col.find_one_and_update(
            {"_id": obj_id},
            {"$set": update_data},
            return_document=True
        )
    except Exception as e:
        if "duplicate key" in str(e).lower() or "e11000" in str(e).lower():
            raise ValueError(f"Another customer with phone number '{update_data.get('phone')}' already exists.")
        raise
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
    """Get list of distinct platform user names from registered users (source filter shows only users)."""
    users_col = get_users_collection()
    users = users_col.distinct("username")
    return sorted(list(set(str(u).strip() for u in users if u and str(u).strip())))

def get_unique_cities() -> list[str]:
    """Get sorted list of distinct city names in small letters."""
    col = get_customers_collection()
    cities = col.distinct("city")
    valid_cities = set()
    for c in cities:
        if c:
            c_clean = str(c).strip().lower()
            if c_clean not in INVALID_LOCATION_VALS:
                valid_cities.add(c_clean)
    return sorted(list(valid_cities))

def get_unique_states() -> list[str]:
    """Get sorted list of distinct state names in small letters."""
    col = get_customers_collection()
    states = col.distinct("state")
    valid_states = set()
    for s in states:
        if s:
            s_clean = str(s).strip().lower()
            if s_clean not in INVALID_LOCATION_VALS:
                valid_states.add(s_clean)
    return sorted(list(valid_states))

def get_dashboard_stats() -> dict[str, Any]:
    """Compute dashboard analytics, metrics, and graph data."""
    col = get_customers_collection()
    now = datetime.now(timezone.utc)
    
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    
    total = col.count_documents({})
    today_count = col.count_documents({"created_at": {"$gte": today_start}})
    week_count = col.count_documents({"created_at": {"$gte": week_start}})
    month_count = col.count_documents({"created_at": {"$gte": month_start}})
    
    # 1. Sources breakdown
    sources_pipeline = [
        {"$group": {"_id": {"$ifNull": ["$from", "Customer"]}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    sources_breakdown = {
        item["_id"]: item["count"] for item in col.aggregate(sources_pipeline)
    }
    
    # 2. Top cities (small letters, case-insensitive group, nil/null excluded)
    cities_pipeline = [
        {
            "$match": {
                "city": {
                    "$ne": None,
                    "$nin": ["", "nil", "NIL", "null", "NULL", "none", "NONE", "na", "NA", "n/a", "N/A", "-", "--"]
                }
            }
        },
        {
            "$group": {
                "_id": {"$toLower": {"$trim": {"input": "$city"}}},
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": 7}
    ]
    top_cities = [
        {"city": item["_id"], "count": item["count"]}
        for item in col.aggregate(cities_pipeline)
        if item["_id"] not in INVALID_LOCATION_VALS
    ]

    # 3. Top states (small letters, case-insensitive group, nil/null excluded)
    states_pipeline = [
        {
            "$match": {
                "state": {
                    "$ne": None,
                    "$nin": ["", "nil", "NIL", "null", "NULL", "none", "NONE", "na", "NA", "n/a", "N/A", "-", "--"]
                }
            }
        },
        {
            "$group": {
                "_id": {"$toLower": {"$trim": {"input": "$state"}}},
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": 7}
    ]
    top_states = [
        {"state": item["_id"], "count": item["count"]}
        for item in col.aggregate(states_pipeline)
        if item["_id"] not in INVALID_LOCATION_VALS
    ]

    # 4. Daily Leads Graph Trend (Last 7 Days)
    days_map = {}
    for i in range(6, -1, -1):
        day_date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        days_map[day_date] = 0

    daily_pipeline = [
        {"$match": {"created_at": {"$gte": now - timedelta(days=7)}}},
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "count": {"$sum": 1}
            }
        }
    ]
    try:
        for row in col.aggregate(daily_pipeline):
            d_key = row["_id"]
            if d_key in days_map:
                days_map[d_key] = row["count"]
    except Exception:
        pass

    chart_daily_labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%d %b") for d in days_map.keys()]
    chart_daily_values = list(days_map.values())
    
    return {
        "total_customers": total,
        "today_count": today_count,
        "this_week_count": week_count,
        "this_month_count": month_count,
        "sources_breakdown": sources_breakdown,
        "top_cities": top_cities,
        "top_states": top_states,
        "chart_daily_labels": chart_daily_labels,
        "chart_daily_values": chart_daily_values,
    }
