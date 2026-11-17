from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services import user_service
from app.models import UserCreate

client = TestClient(app)

def get_or_create_test_user():
    username = f"TestPlatform_{settings.PORT}"
    users = user_service.list_users()
    for u in users:
        if u.username == username:
            return u
    return user_service.create_user(UserCreate(username=username, email="test@platform.com", notes="Test Suite User"))

def test_health_check():
    # Health check is public
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "timestamp" in data

def test_api_requires_both_secret_key_and_user_api_key():
    test_user = get_or_create_test_user()
    valid_sk = settings.SECRET_KEY
    valid_ak = test_user.api_key

    # 1. No keys at all -> 401
    res1 = client.post("/api/customers", json={"phone": "9998887776"})
    assert res1.status_code == 401
    assert "Valid SECRET_KEY is required" in res1.json()["detail"]

    # 2. Only SECRET_KEY (missing User API Key) -> 401
    res2 = client.post(
        "/api/customers",
        headers={"X-Secret-Key": valid_sk},
        json={"phone": "9998887776"}
    )
    assert res2.status_code == 401
    assert "Valid User API Key is required" in res2.json()["detail"]

    # 3. Only User API Key (missing SECRET_KEY) -> 401
    res3 = client.post(
        "/api/customers",
        headers={"X-API-Key": valid_ak},
        json={"phone": "9998887776"}
    )
    assert res3.status_code == 401
    assert "Valid SECRET_KEY is required" in res3.json()["detail"]

    # 4. Invalid User API Key -> 401
    res4 = client.post(
        "/api/customers",
        headers={"X-Secret-Key": valid_sk, "X-API-Key": "invalid_random_key"},
        json={"phone": "9998887776"}
    )
    assert res4.status_code == 401
    assert "invalid or has been deactivated" in res4.json()["detail"]

    # 5. GET customers without both keys -> 401
    get_res = client.get("/api/customers")
    assert get_res.status_code == 401

def test_create_customer_with_both_keys():
    test_user = get_or_create_test_user()
    valid_sk = settings.SECRET_KEY
    valid_ak = test_user.api_key

    response = client.post(
        "/api/customers",
        headers={
            "X-Secret-Key": valid_sk,
            "X-API-Key": valid_ak,
        },
        json={
            "phone": "9998887776",
            "name": "Rohan Sharma",
            "city": "Jaipur"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["phone"] == "9998887776"
    # When submitted via User API Key, 'from' is automatically set to the user's username
    assert data["data"]["from"] == test_user.username

def test_get_customers_with_both_keys():
    test_user = get_or_create_test_user()
    valid_sk = settings.SECRET_KEY
    valid_ak = test_user.api_key

    response = client.get(
        "/api/customers",
        headers={
            "X-Secret-Key": valid_sk,
            "X-API-Key": valid_ak,
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "items" in data
    assert "total" in data

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
    assert "Export Excel" in dash_auth.text

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
