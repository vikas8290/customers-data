from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services import user_service
from app.models import UserCreate

client = TestClient(app)

def test_health_check():
    # Health check is public
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "timestamp" in data

def test_api_requires_secret_key():
    # POST without secret key must fail with 401
    bad_post = client.post(
        "/api/customers",
        json={"phone": "9998887776"}
    )
    assert bad_post.status_code == 401
    assert "Valid API Key or SECRET_KEY is required" in bad_post.json()["detail"]

    # GET without secret key must fail with 401
    bad_get = client.get("/api/customers")
    assert bad_get.status_code == 401

def test_create_customer_with_secret_key_header():
    # Header: X-Secret-Key
    response = client.post(
        "/api/customers",
        headers={"X-Secret-Key": settings.SECRET_KEY},
        json={"phone": "9998887776"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["phone"] == "9998887776"
    assert data["data"]["from"] == "website"

def test_create_customer_with_bearer_token():
    # Authorization: Bearer <SECRET_KEY>
    payload = {
        "phone": "+91 9123456789",
        "name": "Aman Verma",
        "email": "aman@test.com",
        "city": "Bengaluru",
        "from": "landing-campaign"
    }
    response = client.post(
        "/api/customers",
        headers={"Authorization": f"Bearer {settings.SECRET_KEY}"},
        json=payload
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["phone"] == "+91 9123456789"
    assert data["data"]["city"] == "Bengaluru"

def test_user_registration_and_platform_lead_tagging():
    # 1. Admin registers a new platform user (e.g. "Shopify App")
    username = f"Shopify_Test_{settings.PORT}"
    try:
        user = user_service.create_user(UserCreate(username=username, email="shopify@test.com", notes="Shopify store"))
    except ValueError:
        # If already exists from previous run, get by username
        users = user_service.list_users()
        user = [u for u in users if u.username == username][0]

    api_key = user.api_key
    assert api_key.startswith("key_live_")

    # 2. User submits customer data via their unique API Key
    cust_payload = {
        "phone": "9911223344",
        "name": "Shopify Buyer",
        "city": "Pune",
    }
    resp = client.post(
        "/api/customers",
        headers={"X-API-Key": api_key},
        json=cust_payload
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    # The customer's 'from' column MUST be automatically set to the User's name!
    assert data["data"]["from"] == username
    print(f"Verified customer 'from' column is set to platform user: {data['data']['from']}")

    # 3. Filter customer list by this platform/user name
    filter_resp = client.get(
        f"/api/customers?from={username}",
        headers={"X-API-Key": api_key}
    )
    assert filter_resp.status_code == 200
    filter_data = filter_resp.json()
    assert filter_data["total"] >= 1
    assert all(item["from"] == username for item in filter_data["items"])
    print(f"Verified filtering by platform '{username}' returns matched leads!")

def test_login_flow_and_dashboard():
    if not settings.ADMIN_PASSWORD:
        settings.ADMIN_PASSWORD = "testpassword123"
        settings.ADMIN_USERNAME = "admin"

    # 1. Access dashboard without login -> redirects to login
    dash_resp = client.get("/dashboard", follow_redirects=False)
    assert dash_resp.status_code == 302
    assert dash_resp.headers["location"] == "/login"

    # 2. Login with correct credentials
    good_login = client.post(
        "/login",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        follow_redirects=False
    )
    assert good_login.status_code == 302
    assert good_login.headers["location"] == "/dashboard"
    
    cookies = good_login.cookies

    # 3. Access dashboard with session cookies -> 200 OK
    dash_auth = client.get("/dashboard", cookies=cookies)
    assert dash_auth.status_code == 200
    assert "Customer Records" in dash_auth.text
    assert "Platform Users & API Keys" in dash_auth.text

    # 4. Export excel with session cookies -> 200 OK
    export_resp = client.get("/export/excel", cookies=cookies)
    assert export_resp.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in export_resp.headers["content-type"]

    # 5. Access dedicated /users page with session cookies -> 200 OK
    users_auth = client.get("/users", cookies=cookies)
    assert users_auth.status_code == 200
    assert "Platform Users & API Keys" in users_auth.text
    assert "Register New Platform / User" in users_auth.text
    print("✓ Dedicated /users page loads successfully with 200 OK")

print("All tests defined!")
