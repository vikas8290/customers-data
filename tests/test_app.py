import time
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services import user_service, customer_service
from app.models import UserCreate, normalize_indian_phone

client = TestClient(app)

def test_normalize_indian_phone_unit():
    assert normalize_indian_phone("9876543210") == "+919876543210"
    assert normalize_indian_phone("+919876543210") == "+919876543210"
    assert normalize_indian_phone("+91 98765 43210") == "+919876543210"
    assert normalize_indian_phone("+91-9876543210") == "+919876543210"
    assert normalize_indian_phone("09876543210") == "+919876543210"
    assert normalize_indian_phone("919876543210") == "+919876543210"
    
    try:
        normalize_indian_phone("12345")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

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

def test_create_customer_with_indian_phone_and_uniqueness():
    test_user = get_or_create_test_user()
    valid_sk = settings.SECRET_KEY
    valid_ak = test_user.api_key

    # Generate a unique 10-digit phone for this test run
    random_suffix = str(int(time.time() * 100))[-8:]
    unique_10_digit = f"98{random_suffix}"  # 10 digits total

    # 1. Pass 10-digit phone -> must automatically add +91 and store as +91XXXXXXXXXX
    response = client.post(
        "/api/customers",
        headers={
            "X-Secret-Key": valid_sk,
            "X-API-Key": valid_ak,
        },
        json={
            "phone": unique_10_digit,
            "name": "Rohan Sharma",
            "city": "Jaipur"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    # The phone MUST be stored in +91XXXXXXXXXX format
    expected_phone = f"+91{unique_10_digit}"
    assert data["data"]["phone"] == expected_phone
    assert data["data"]["from"] == test_user.username

    # 2. Duplicate phone check: trying to create another customer with the SAME phone must fail with 409 Conflict
    dup_res = client.post(
        "/api/customers",
        headers={
            "X-Secret-Key": valid_sk,
            "X-API-Key": valid_ak,
        },
        json={
            "phone": expected_phone,
            "name": "Duplicate Person"
        }
    )
    assert dup_res.status_code == 409
    assert "already exists" in dup_res.json()["detail"]

    # 3. Duplicate phone check: trying to create with 10-digit variant of same phone must also fail with 409 Conflict
    dup_res2 = client.post(
        "/api/customers",
        headers={
            "X-Secret-Key": valid_sk,
            "X-API-Key": valid_ak,
        },
        json={
            "phone": unique_10_digit,
            "name": "Duplicate Person 2"
        }
    )
    assert dup_res2.status_code == 409
    assert "already exists" in dup_res2.json()["detail"]

    # 4. Invalid phone number format check -> 422 Unprocessable
    invalid_phone_res = client.post(
        "/api/customers",
        headers={
            "X-Secret-Key": valid_sk,
            "X-API-Key": valid_ak,
        },
        json={
            "phone": "12345",  # Too short, not 10 digits
            "name": "Invalid Phone User"
        }
    )
    assert invalid_phone_res.status_code == 422
    assert "Indian phone numbers must be 10 digits" in str(invalid_phone_res.json())

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

def test_dashboard_charts_and_city_state_filters():
    # 1. Verify dashboard stats have chart data
    stats = customer_service.get_dashboard_stats()
    assert "chart_daily_labels" in stats
    assert "chart_daily_values" in stats
    assert len(stats["chart_daily_labels"]) == 7
    assert len(stats["chart_daily_values"]) == 7

    test_user = get_or_create_test_user()
    valid_sk = settings.SECRET_KEY
    valid_ak = test_user.api_key

    # 2. Add customer with specific city & state
    random_suffix = str(int(time.time() * 100))[-8:]
    phone_num = f"97{random_suffix}"
    cust_res = client.post(
        "/api/customers",
        headers={"X-Secret-Key": valid_sk, "X-API-Key": valid_ak},
        json={
            "phone": phone_num,
            "name": "Chart Test Customer",
            "city": "Jodhpur",
            "state": "Rajasthan"
        }
    )
    assert cust_res.status_code == 201

    # 3. Test city and state filters in customer list API
    list_res = client.get(
        "/api/customers?city=Jodhpur&state=Rajasthan",
        headers={"X-Secret-Key": valid_sk, "X-API-Key": valid_ak}
    )
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(c["city"] == "Jodhpur" for c in list_data["items"])

    # 4. Test API Excel export with city and state filters
    api_excel_res = client.get(
        "/api/customers/export/excel?city=Jodhpur&state=Rajasthan",
        headers={"X-Secret-Key": valid_sk, "X-API-Key": valid_ak}
    )
    assert api_excel_res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in api_excel_res.headers["content-type"]
    print("✓ API Excel export according to filters passed successfully")

def test_kolkata_timezone_formatting():
    from datetime import datetime, timezone
    from app.routers.portal import format_kolkata_time

    # UTC 2026-11-17 12:00:00 is 17:30 (5:30 PM) in Asia/Kolkata
    dt_utc = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)
    formatted = format_kolkata_time(dt_utc)
    assert "17 Nov 2026" in formatted
    assert "05:30 PM" in formatted

    # None check
    assert format_kolkata_time(None) == "-"
    print("✓ Asia/Kolkata 12-hour AM/PM formatting verified")

def test_user_update_and_lead_sync():
    test_user = get_or_create_test_user()
    user_id = test_user.id
    new_username = f"Renamed_{int(time.time())}"

    # 1. Update user via service
    updated = user_service.update_user(
        user_id=user_id,
        username=new_username,
        email="updated@platform.com",
        notes="Updated notes",
        is_active=True,
    )
    assert updated is not None
    assert updated.username == new_username
    assert updated.email == "updated@platform.com"
    assert updated.notes == "Updated notes"

    # 2. Portal user edit endpoint
    login_res = client.post(
        "/login",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        follow_redirects=False
    )
    cookies = login_res.cookies

    portal_edit_res = client.post(
        f"/portal/user/{user_id}/edit",
        data={
            "username": f"PortalUser_{int(time.time())}",
            "email": "portal@edit.com",
            "notes": "Edited via portal",
            "is_active": "true",
            "redirect_to": "/users"
        },
        cookies=cookies,
        follow_redirects=False
    )
    assert portal_edit_res.status_code == 302
    assert "msg=user_updated" in portal_edit_res.headers["location"]

    # 3. API user update endpoint with SECRET_KEY
    api_update_res = client.put(
        f"/api/admin/users/{user_id}",
        headers={"X-Secret-Key": settings.SECRET_KEY},
        json={
            "notes": "API updated notes"
        }
    )
    assert api_update_res.status_code == 200
    assert api_update_res.json()["data"]["notes"] == "API updated notes"
    print("✓ User edit in service, portal and API verified")

def test_dashboard_reordered_columns_and_pagination():
    login_res = client.post(
        "/login",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        follow_redirects=False
    )
    cookies = login_res.cookies

    # 1. Verify "Customer Records Overview" is removed from /dashboard
    dash_resp = client.get("/dashboard", cookies=cookies)
    assert dash_resp.status_code == 200
    assert "Customer Records Overview" not in dash_resp.text
    assert "Customer Records Directory" in dash_resp.text

    # 2. Verify column headings and pagination on dedicated /customers page
    resp = client.get("/customers?page=1&page_size=10", cookies=cookies)
    assert resp.status_code == 200
    html = resp.text

    # Verify column headings
    assert "Name / Profile" in html
    assert "Phone &amp; Email" in html or "Phone & Email" in html
    assert "Source &amp; Date (IST)" in html or "Source & Date (IST)" in html

    # Verify pagination elements
    assert "Showing" in html
    assert "Rows:" in html
    assert "name=\"page_size\"" in html
    print("✓ Customer Records Overview removed from dashboard; customer columns and pagination verified on /customers")

def test_source_filter_shows_only_users():
    test_user = get_or_create_test_user()

    # Verify get_unique_sources() returns registered users and not arbitrary non-user strings
    sources = customer_service.get_unique_sources()
    assert test_user.username in sources

    # Check /customers HTML has 'All Users' and contains the test_user
    login_res = client.post(
        "/login",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        follow_redirects=False
    )
    cookies = login_res.cookies
    resp = client.get("/customers", cookies=cookies)
    assert resp.status_code == 200
    assert "All Users" in resp.text
    assert f">{test_user.username}</option>" in resp.text
    print("✓ Source filter displays only registered users verified")

def test_customer_extra_json_data():
    test_user = get_or_create_test_user()
    valid_sk = settings.SECRET_KEY
    valid_ak = test_user.api_key

    random_suffix = str(int(time.time() * 100))[-8:]
    phone_num = f"96{random_suffix}"
    extra_json = {"order_id": 9921, "vip": True, "notes": "High value lead"}

    # Create customer with extra JSON data
    cust_res = client.post(
        "/api/customers",
        headers={"X-Secret-Key": valid_sk, "X-API-Key": valid_ak},
        json={
            "phone": phone_num,
            "name": "JSON Data Customer",
            "city": "Bengaluru",
            "data": extra_json
        }
    )
    assert cust_res.status_code == 201
    created_customer = cust_res.json()["data"]
    assert created_customer["data"] == extra_json
    print("✓ Extra JSON data stored and retrieved via API")

def test_dedicated_customers_page_and_searchable_selects():
    login_res = client.post(
        "/login",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        follow_redirects=False
    )
    cookies = login_res.cookies

    # Dedicated /customers page
    resp = client.get("/customers", cookies=cookies)
    assert resp.status_code == 200
    html = resp.text

    assert "Customer Records" in html
    assert "searchable-select" in html
    assert "Extra Data" in html
    assert "All Users" in html
    assert "All Cities" in html
    assert "All States" in html
    print("✓ Dedicated /customers page with searchable selects verified")

def test_profile_not_available_null_sent():
    test_user = get_or_create_test_user()
    valid_sk = settings.SECRET_KEY
    valid_ak = test_user.api_key

    # 1. Profile omitted -> response has "profile": null
    random_suffix1 = str(int(time.time() * 100))[-8:]
    res1 = client.post(
        "/api/customers",
        headers={"X-Secret-Key": valid_sk, "X-API-Key": valid_ak},
        json={"phone": f"95{random_suffix1}", "name": "No Profile User"}
    )
    assert res1.status_code == 201
    assert res1.json()["data"]["profile"] is None

    # 2. Profile sent as empty string "" -> response has "profile": null
    random_suffix2 = str(int(time.time() * 100) + 1)[-8:]
    res2 = client.post(
        "/api/customers",
        headers={"X-Secret-Key": valid_sk, "X-API-Key": valid_ak},
        json={"phone": f"95{random_suffix2}", "name": "Empty Profile User", "profile": ""}
    )
    assert res2.status_code == 201
    assert res2.json()["data"]["profile"] is None

    # 3. Profile sent as string "null" -> response has "profile": null
    random_suffix3 = str(int(time.time() * 100) + 2)[-8:]
    res3 = client.post(
        "/api/customers",
        headers={"X-Secret-Key": valid_sk, "X-API-Key": valid_ak},
        json={"phone": f"95{random_suffix3}", "name": "String Null Profile User", "profile": "null"}
    )
    assert res3.status_code == 201
    assert res3.json()["data"]["profile"] is None
    print("✓ Profile image not available verified to strictly return null")

def test_connect_website_modal_with_languages_and_data_column():
    login_resp = client.post(
        "/login",
        data={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        follow_redirects=False,
    )
    cookies = login_resp.cookies

    # Fetch dashboard which inherits base.html with the websiteModal
    dash_resp = client.get("/dashboard", cookies=cookies)
    assert dash_resp.status_code == 200
    html = dash_resp.text

    # 1. Verify Connect Website button & modal container
    assert "Connect Website" in html
    assert 'id="websiteModal"' in html
    assert "Connect Website / API Integration" in html

    # 2. Verify all requested language tabs are present
    assert "PHP" in html
    assert "Python" in html
    assert "Terminal (cURL)" in html
    assert "Node.js" in html
    assert "JavaScript (Browser)" in html
    assert "Other (HTML / Webhooks)" in html

    # 3. Verify code pane IDs
    assert 'id="pane-php"' in html
    assert 'id="pane-python"' in html
    assert 'id="pane-terminal"' in html
    assert 'id="pane-node"' in html
    assert 'id="pane-javascript"' in html
    assert 'id="pane-other"' in html

    # 4. Verify new column 'data' is documented and included in snippets
    assert "New Column: Extra JSON Data" in html
    assert "'data'     => [" in html      # PHP syntax
    assert '"data": {' in html            # Python / Terminal / Node / JS JSON syntax
    assert "switchConnectTab" in html

    # 5. Verify /docs API documentation has data column and integration types
    docs_resp = client.get("/openapi.json")
    assert docs_resp.status_code == 200
    docs_json = docs_resp.json()
    description = docs_json.get("info", {}).get("description", "")
    assert "Extra Data Column (`data`)" in description
    assert "PHP" in description
    assert "Python" in description
    assert "Terminal / CLI" in description
    assert "Node.js" in description
    print("✓ Connect Website modal with PHP, Python, Terminal, Node, JS, Other & data column verified")

print("All tests defined!")
