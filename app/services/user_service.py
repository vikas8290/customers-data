import secrets
from datetime import datetime, timezone
from typing import Optional, Any
from bson import ObjectId
from pymongo import DESCENDING
from app.database import get_users_collection, get_customers_collection
from app.models import UserCreate, UserInDB

DEFAULT_CUSTOMER_USERNAME = "Customer"
DEFAULT_CUSTOMER_EMAIL = "portal@customer.com"
DEFAULT_CUSTOMER_API_KEY = "key_live_4cd32dfa2caa35276ca9f53446267f9c"

def ensure_default_customer_user() -> UserInDB:
    """
    Ensure the standard default platform user 'Customer' exists with
    portal@customer.com and fixed API key key_live_4cd32dfa2caa35276ca9f53446267f9c.
    """
    col = get_users_collection()
    user = col.find_one({
        "$or": [
            {"username": DEFAULT_CUSTOMER_USERNAME},
            {"email": DEFAULT_CUSTOMER_EMAIL},
            {"api_key": DEFAULT_CUSTOMER_API_KEY}
        ]
    })
    now = datetime.now(timezone.utc)
    if not user:
        doc = {
            "username": DEFAULT_CUSTOMER_USERNAME,
            "email": DEFAULT_CUSTOMER_EMAIL,
            "notes": "Default Platform User",
            "api_key": DEFAULT_CUSTOMER_API_KEY,
            "is_active": True,
            "created_at": now,
            "last_used_at": None,
        }
        res = col.insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc_to_user(doc)
    else:
        updates = {}
        if user.get("username") != DEFAULT_CUSTOMER_USERNAME:
            updates["username"] = DEFAULT_CUSTOMER_USERNAME
        if user.get("email") != DEFAULT_CUSTOMER_EMAIL:
            updates["email"] = DEFAULT_CUSTOMER_EMAIL
        if user.get("api_key") != DEFAULT_CUSTOMER_API_KEY:
            updates["api_key"] = DEFAULT_CUSTOMER_API_KEY
        if not user.get("is_active"):
            updates["is_active"] = True
        if updates:
            col.update_one({"_id": user["_id"]}, {"$set": updates})
            user.update(updates)
        return doc_to_user(user)

def doc_to_user(doc: dict[str, Any], leads_count: int = 0) -> UserInDB:
    """Helper to convert MongoDB user document to UserInDB model."""
    doc_copy = dict(doc)
    doc_copy["id"] = str(doc_copy.pop("_id"))
    doc_copy["leads_count"] = leads_count
    return UserInDB(**doc_copy)

def generate_api_key(prefix: str = "key_live") -> str:
    """Generate a secure, random API key."""
    return f"{prefix}_{secrets.token_hex(16)}"

def create_user(data: UserCreate) -> UserInDB:
    """Register a new user / platform and generate an API key."""
    col = get_users_collection()
    username = data.username.strip()
    
    # Check if username already exists
    existing = col.find_one({"username": {"$regex": f"^{username}$", "$options": "i"}})
    if existing:
        raise ValueError(f"User / Platform '{username}' already exists.")

    api_key = generate_api_key()
    now = datetime.now(timezone.utc)

    doc = {
        "username": username,
        "email": data.email.strip().lower() if data.email else None,
        "notes": data.notes.strip() if data.notes else None,
        "api_key": api_key,
        "is_active": True,
        "created_at": now,
        "last_used_at": None,
    }

    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc_to_user(doc, leads_count=0)

def get_user_by_api_key(api_key: str) -> Optional[UserInDB]:
    """Retrieve an active user by their API key."""
    if not api_key:
        return None
    ak = api_key.strip()
    col = get_users_collection()
    doc = col.find_one({"api_key": ak, "is_active": True})
    if not doc:
        if ak == DEFAULT_CUSTOMER_API_KEY:
            return ensure_default_customer_user()
        return None
    
    # Update last_used_at
    col.update_one({"_id": doc["_id"]}, {"$set": {"last_used_at": datetime.now(timezone.utc)}})
    return doc_to_user(doc)

def get_user_by_id(user_id: str) -> Optional[UserInDB]:
    """Retrieve user by ObjectId."""
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        return None
    col = get_users_collection()
    doc = col.find_one({"_id": obj_id})
    if not doc:
        return None
    
    # Count leads
    cust_col = get_customers_collection()
    leads = cust_col.count_documents({"from": doc.get("username")})
    return doc_to_user(doc, leads_count=leads)

def list_users() -> list[UserInDB]:
    """List all registered users with lead count statistics."""
    col = get_users_collection()
    cust_col = get_customers_collection()

    # Aggregate lead counts by source
    lead_counts_pipeline = [
        {"$group": {"_id": "$from", "count": {"$sum": 1}}}
    ]
    leads_map = {item["_id"]: item["count"] for item in cust_col.aggregate(lead_counts_pipeline)}

    users = []
    for doc in col.find().sort("created_at", DESCENDING):
        uname = doc.get("username")
        count = leads_map.get(uname, 0)
        users.append(doc_to_user(doc, leads_count=count))
        
    return users

def delete_user(user_id: str) -> bool:
    """Delete a user and revoke their API key. Default Customer user cannot be deleted."""
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        return False
    col = get_users_collection()
    user_doc = col.find_one({"_id": obj_id})
    if user_doc and user_doc.get("username") == DEFAULT_CUSTOMER_USERNAME:
        raise ValueError(f"Cannot delete standard default platform user '{DEFAULT_CUSTOMER_USERNAME}'.")
    res = col.delete_one({"_id": obj_id})
    return res.deleted_count > 0

def update_user(
    user_id: str,
    username: Optional[str] = None,
    email: Optional[str] = None,
    notes: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[UserInDB]:
    """Update user / platform details with duplicate name prevention."""
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        return None
    
    col = get_users_collection()
    user_doc = col.find_one({"_id": obj_id})
    if not user_doc:
        return None
        
    old_username = user_doc.get("username")
    update_data: dict[str, Any] = {}

    if username and username.strip():
        new_uname = username.strip()
        if new_uname.lower() != (old_username or "").lower():
            existing = col.find_one({
                "username": {"$regex": f"^{new_uname}$", "$options": "i"},
                "_id": {"$ne": obj_id}
            })
            if existing:
                raise ValueError(f"User / Platform '{new_uname}' already exists.")
            update_data["username"] = new_uname
            # Sync leads to the updated platform name
            cust_col = get_customers_collection()
            cust_col.update_many({"from": old_username}, {"$set": {"from": new_uname}})

    if email is not None:
        update_data["email"] = email.strip().lower() if email.strip() else None

    if notes is not None:
        update_data["notes"] = notes.strip() if notes.strip() else None

    if is_active is not None:
        update_data["is_active"] = bool(is_active)

    if not update_data:
        return get_user_by_id(user_id)

    col.update_one({"_id": obj_id}, {"$set": update_data})
    return get_user_by_id(user_id)

def regenerate_api_key(user_id: str) -> Optional[str]:
    """Regenerate a new API key for the user."""
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        return None
    
    new_key = generate_api_key()
    col = get_users_collection()
    res = col.update_one({"_id": obj_id}, {"$set": {"api_key": new_key}})
    return new_key if res.modified_count > 0 else None
