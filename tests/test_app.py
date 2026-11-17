from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "timestamp" in data

def test_create_customer_minimal_phone_only():
    # Only phone is required
    response = client.post(
        "/api/customers",
        json={"phone": "9998887776"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["phone"] == "9998887776"
    assert data["data"]["from"] == "website"

def test_create_customer_all_fields():
    payload = {
        "phone": "+91 9123456789",
        "name": "Aman Verma",
        "email": "aman@test.com",
        "profile": "Software Engineer",
        "address": "45 Lake View Road",
        "landmark": "Opposite City Park",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pincode": "560001",
        "from": "landing-campaign"
    }
    response = client.post("/api/customers", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["phone"] == "+91 9123456789"
    assert data["data"]["name"] == "Aman Verma"
    assert data["data"]["city"] == "Bengaluru"
    assert data["data"]["from"] == "landing-campaign"

def test_create_customer_missing_phone_fails():
    # Missing phone must fail validation
    response = client.post(
        "/api/customers",
        json={"name": "No Phone User"}
    )
    assert response.status_code == 422

def test_create_customer_form_data():
    form_data = {
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

def test_get_customers_api():
    response = client.get("/api/customers?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "items" in data
    assert len(data["items"]) >= 1

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
    print("Exported Excel file size:", len(export_resp.content), "bytes")

print("All tests defined!")
