from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

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
    assert "SECRET_KEY is required" in bad_post.json()["detail"]

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

def test_create_customer_missing_phone_fails():
    # Valid secret key but missing required phone
    response = client.post(
        "/api/customers",
        headers={"X-Secret-Key": settings.SECRET_KEY},
        json={"name": "No Phone User"}
    )
    assert response.status_code == 422

def test_create_customer_with_body_secret_key():
    # Secret key embedded in Form/JSON body
    form_data = {
        "secret_key": settings.SECRET_KEY,
        "phone": "9811122233",
        "name": "Form Submitter",
        "city": "Delhi",
        "from": "contact-page-form"
    }
    response = client.post("/api/customers", data=form_data)
    assert response.status_code == 201
    data = response.json()
    assert data["data"]["phone"] == "9811122233"
    assert data["data"]["from"] == "contact-page-form"

def test_get_customers_api_with_secret_key():
    # Header
    response = client.get(
        "/api/customers?page=1&page_size=5",
        headers={"X-Secret-Key": settings.SECRET_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "items" in data
    assert len(data["items"]) >= 1

    # Query param: ?secret_key=...
    query_resp = client.get(f"/api/customers?page=1&page_size=5&secret_key={settings.SECRET_KEY}")
    assert query_resp.status_code == 200

def test_login_flow_and_dashboard():
    # Ensure credentials exist for test
    if not settings.ADMIN_PASSWORD:
        settings.ADMIN_PASSWORD = "testpassword123"
        settings.ADMIN_USERNAME = "admin"

    # 1. Access dashboard without login -> redirects to login
    dash_resp = client.get("/dashboard", follow_redirects=False)
    assert dash_resp.status_code == 302
    assert dash_resp.headers["location"] == "/login"

    # 2. Login with bad credentials -> 401
    bad_login = client.post(
        "/login",
        data={"username": "admin", "password": "wrongpassword"}
    )
    assert bad_login.status_code == 401

    # 3. Login with correct credentials
    good_login = client.post(
        "/login",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        follow_redirects=False
    )
    assert good_login.status_code == 302
    assert good_login.headers["location"] == "/dashboard"
    
    # Extract cookies
    cookies = good_login.cookies

    # 4. Access dashboard with session cookies -> 200 OK
    dash_auth = client.get("/dashboard", cookies=cookies)
    assert dash_auth.status_code == 200
    assert "Customer Records" in dash_auth.text

    # 5. Export excel with session cookies -> 200 OK and Excel content-type
    export_resp = client.get("/export/excel", cookies=cookies)
    assert export_resp.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in export_resp.headers["content-type"]
    assert len(export_resp.content) > 1000

print("All tests defined!")
