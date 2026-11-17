# Customer Data Collection & Admin Portal System

A complete, production-ready Python web application for collecting customer leads via REST API / website forms, storing them securely in MongoDB Atlas, managing them via a modern Admin Portal, exporting records to Excel (.xlsx), and deploying seamlessly to Render.

---

## 🌟 Key Features

- **Public REST API & Webhook**:
  - Accept customer leads from websites, landing pages, mobile apps, or contact forms.
  - Supports both **JSON payloads** and standard **HTML Form Data (`multipart/form-data` / `application/x-www-form-urlencoded`)**.
  - **CORS enabled**: Any website frontend can post data directly without CORS errors.
  - Interactive Swagger UI documentation at `/docs` and ReDoc at `/redoc`.
- **Platform Users & API Keys Management**:
  - Admin can register multiple platforms / users (e.g., `Shopify Store`, `WordPress Site`, `Landing Page A`, `Partner Client`).
  - Automatically generates a unique API key (`key_live_...`) for each user.
  - When leads are submitted using that user's API key, their **username is automatically tagged in the customer's `from` column**.
  - Admin can filter all customer leads by platform with a single click.
- **Customer Data Schema**:
  - **`phone`** (*Required* - primary customer identifier)
  - **`name`** (*Optional*)
  - **`email`** (*Optional*)
  - **`profile`** (*Optional* - avatar URL, notes, or role)
  - **`address`** (*Optional*)
  - **`landmark`** (*Optional*)
  - **`pincode`** (*Optional*)
  - **`city`** (*Optional*)
  - **`state`** (*Optional*)
  - **`from`** (*Optional* - tracks lead channel, e.g. `website`, `landing-page`, `instagram`, default: `website`)
  - **`created_at`** (Auto UTC timestamp)
- **Modern Admin Portal**:
  - Secure session-based authentication (`/login`, `/dashboard`, `/logout`).
  - Real-time statistics: Total customers, today's registrations, weekly trends, top sources.
  - Live search across phone, name, email, city, address.
  - Filter by traffic source (`from`) and location.
  - View details modal, manual customer entry modal, edit modal, and delete record modal.
- **Excel (.xlsx) Export**:
  - Single-click export of customer records directly to Microsoft Excel.
  - Professional styling: Dark blue header, bold column titles, zebra striping, centered data, and auto-adjusted column widths.
  - Respects active search and source filters or exports all records.
- **MongoDB Atlas Integration**:
  - Pre-configured with the provided MongoDB Atlas connection.
  - Automated indexing on `created_at`, `phone`, and `from` fields for high performance.
- **Render Deployment Ready**:
  - Configured with `Procfile`, `render.yaml`, `requirements.txt`, and standard environment variables.

---

## 🏗️ Project Architecture

```
customers-data/
├── app/
│   ├── __init__.py
│   ├── config.py             # Environment configuration & settings
│   ├── database.py           # MongoDB connection & collection helpers
│   ├── models.py             # Pydantic schemas & data validation
│   ├── auth.py               # Admin authentication & session management
│   ├── services/
│   │   ├── __init__.py
│   │   ├── customer_service.py # CRUD queries, search & aggregations
│   │   └── excel_service.py    # Openpyxl styled Excel (.xlsx) generator
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── api.py            # REST API routes (/api/customers, /api/stats, etc.)
│   │   └── portal.py         # Admin web portal routes (/login, /dashboard, /export)
│   ├── templates/            # Jinja2 HTML templates (Tailwind CSS + Lucide Icons)
│   │   ├── base.html         # Master layout
│   │   ├── login.html        # Admin sign-in screen
│   │   └── dashboard.html    # Full-featured Customer Hub dashboard
│   ├── static/
│   │   └── css/custom.css
│   └── main.py               # FastAPI entrypoint with CORS & Session middlewares
├── tests/
│   └── test_app.py           # Automated test suite (API, Auth, Export)
├── .env                      # Local environment configuration
├── .env.example              # Template environment variables
├── .gitignore
├── Procfile                  # Process definition for Render / PaaS
├── render.yaml               # Render Infrastructure-as-Code Blueprint
├── requirements.txt          # Python dependencies
└── README.md                 # Complete documentation & deployment guide
```

---

## 🚀 Quick Start (Local Setup)

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd customers-data
```

### 2. Create and activate a Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root (or copy from `.env.example`):
```ini
PORT=8000
HOST=0.0.0.0
SECRET_KEY=your-super-secret-key-12345

# MongoDB Atlas
MONGO_URI=mongodb+srv://vikashkumawat1007_db_user:uFNj1xDgFM9ONAtp@cluster0.e0tcnaf.mongodb.net/
DATABASE_NAME=customer_portal_db
COLLECTION_NAME=customers

# Admin Portal Login
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password

# CORS
CORS_ORIGINS=*
```

### 5. Run the Server
```bash
uvicorn app.main:app --reload --port 8000
```

Open your browser:
- **Admin Portal**: [http://localhost:8000/login](http://localhost:8000/login) (Sign in with credentials set in your `.env`)
- **Interactive API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 📡 API Reference & Website Integration

### 1. Collect Customer Data (`POST /api/customers`)
Any website, landing page, or frontend form can send customer data to this endpoint.

#### 🔒 Secret Key Authentication Required:
To prevent unauthorized spam and protect customer data, all API endpoints require your configured `SECRET_KEY`.
You can pass it in **any** of the following ways:
- **Header**: `X-Secret-Key: <YOUR_SECRET_KEY>` *(Recommended)*
- **Header**: `Authorization: Bearer <YOUR_SECRET_KEY>`
- **Query Parameter**: `?secret_key=<YOUR_SECRET_KEY>`
- **Request Body**: `{"secret_key": "<YOUR_SECRET_KEY>", "phone": "..."}`

#### Only `phone` is required; all other customer fields are optional!

#### A. JSON Request Example (JavaScript `fetch`)
```javascript
// Submit lead from your website
fetch('https://<your-render-domain>.onrender.com/api/customers', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Secret-Key': 'YOUR_SECRET_KEY' // REQUIRED
  },
  body: JSON.stringify({
    phone: "+91 9876543210",       // REQUIRED
    name: "Aman Sharma",          // Optional
    email: "aman@example.com",     // Optional
    profile: "VIP Client",         // Optional
    address: "123 Park Avenue",    // Optional
    landmark: "Near Metro Gate 2", // Optional
    city: "Jaipur",                // Optional
    state: "Rajasthan",            // Optional
    pincode: "302001",             // Optional
    from: "website"                // Optional (source identifier)
  })
})
.then(res => res.json())
.then(data => console.log('Lead submitted:', data))
.catch(err => console.error('Error submitting lead:', err));
```

#### B. cURL Command
```bash
curl -X POST https://<your-render-domain>.onrender.com/api/customers \
  -H "Content-Type: application/json" \
  -H "X-Secret-Key: YOUR_SECRET_KEY" \
  -d '{
    "phone": "9876543210",
    "name": "Rohan Patel",
    "email": "rohan@example.com",
    "city": "Ahmedabad",
    "state": "Gujarat",
    "from": "website"
  }'
```

#### C. Minimal Request (Phone Only)
```bash
curl -X POST https://<your-render-domain>.onrender.com/api/customers \
  -H "Content-Type: application/json" \
  -H "X-Secret-Key: YOUR_SECRET_KEY" \
  -d '{"phone": "9998887776"}'
```

#### Response (HTTP 201 Created):
```json
{
  "success": true,
  "message": "Customer data recorded successfully.",
  "data": {
    "id": "6afc40992f070bae46b5a22a",
    "phone": "9876543210",
    "name": "Rohan Patel",
    "email": "rohan@example.com",
    "profile": null,
    "address": null,
    "landmark": null,
    "pincode": null,
    "city": "Ahmedabad",
    "state": "Gujarat",
    "from": "website",
    "created_at": "2026-11-17T11:45:00.000000Z",
    "updated_at": "2026-11-17T11:45:00.000000Z"
  }
}
```

---

### 2. Standard HTML Form Integration (No JavaScript Required)
You can point any traditional HTML form directly to the API endpoint and embed your `secret_key`:
```html
<form action="https://<your-render-domain>.onrender.com/api/customers" method="POST">
  <!-- Secret key protection -->
  <input type="hidden" name="secret_key" value="YOUR_SECRET_KEY">
  
  <input type="text" name="phone" required placeholder="Enter Phone Number *">
  <input type="text" name="name" placeholder="Full Name">
  <input type="email" name="email" placeholder="Email Address">
  <input type="text" name="city" placeholder="City">
  <input type="hidden" name="from" value="contact-us-page">
  <button type="submit">Submit</button>
</form>
```

---

### 3. Retrieve Customers API (`GET /api/customers`)
Query parameters:
- `search`: Filter text matching phone, name, email, city, address
- `from`: Filter by collection source (e.g. `website`, `landing-page`)
- `city`: Filter by city
- `state`: Filter by state
- `page`: Page number (default: 1)
- `page_size`: Records per page (default: 20, max: 100)

```bash
curl -X GET "https://<your-render-domain>.onrender.com/api/customers?page=1&page_size=20" \
  -H "X-Secret-Key: YOUR_SECRET_KEY"
```

---

### 4. Single Customer Operations
- **Get Customer by ID**: `GET /api/customers/{id}`
- **Update Customer**: `PUT /api/customers/{id}`
- **Delete Customer**: `DELETE /api/customers/{id}`
- **Analytics & Summary**: `GET /api/stats`
- **List Traffic Sources**: `GET /api/sources`

---

## 📊 Excel Export

The admin portal provides an **"Export Excel"** button:
- **URL**: `GET /export/excel`
- Generates an in-memory `.xlsx` spreadsheet matching any active search query or all records.
- Formatted with:
  1. `S.No`
  2. `Customer ID`
  3. `Date & Time (UTC)`
  4. `Phone (Required)`
  5. `Name`
  6. `Email`
  7. `Source (From)`
  8. `Address`
  9. `Landmark`
  10. `City`
  11. `State`
  12. `Pincode`
  13. `Profile / Notes`

---

## ☁️ How to Deploy to Render (Step-by-Step)

### Option A: Standard Web Service Deployment (Recommended)

1. **Commit and Push your project to GitHub**:
   ```bash
   git add .
   git commit -m "Complete Customer Data Hub with API, Portal, MongoDB & Excel Export"
   git push origin main
   ```

2. **Log into Render**:
   - Go to [https://dashboard.render.com](https://dashboard.render.com).

3. **Create New Web Service**:
   - Click the **"New +"** button at the top right and select **"Web Service"**.
   - Select **"Build and deploy from a Git repository"** and connect your GitHub repository `customers-data`.

4. **Configure Service Settings**:
   - **Name**: `customer-data-hub` (or any name you like)
   - **Language / Runtime**: `Python 3`
   - **Branch**: `main`
   - **Region**: Choose the region closest to you (e.g., `Singapore` or `Oregon`)
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: `Free`

5. **Set Environment Variables**:
   Scroll down to the **"Environment Variables"** section and add:

   | Key | Value | Description |
   |---|---|---|
   | `MONGO_URI` | `mongodb+srv://vikashkumawat1007_db_user:uFNj1xDgFM9ONAtp@cluster0.e0tcnaf.mongodb.net/` | MongoDB Atlas Connection URI |
   | `DATABASE_NAME` | `customer_portal_db` | Database Name |
   | `COLLECTION_NAME` | `customers` | Collection Name |
   | `ADMIN_USERNAME` | `admin` | Portal username |
   | `ADMIN_PASSWORD` | `<your-secure-password>` | Portal password |
   | `SECRET_KEY` | `<any-long-random-string>` | Used for session encryption |
   | `CORS_ORIGINS` | `*` | Allows websites to submit leads |

6. **Click "Deploy Web Service"**:
   - Render will build the environment, install the packages, and launch the application.
   - Once deployment completes, Render will provide a live URL, e.g.:
     `https://customer-data-hub.onrender.com`

---

### Option B: Deploy via Render Blueprint (`render.yaml`)

This repository includes a `render.yaml` Blueprint file.
1. In the Render Dashboard, click **"New +"** -> **"Blueprint"**.
2. Select your repository.
3. Render will automatically read `render.yaml` and set up the build command, start command, and environment variable slots.
4. Click **Apply**.

---

## 🧪 Running Automated Tests

Run the included verification suite:
```bash
python -m tests.test_app
```
or with pytest:
```bash
pytest tests/
```

All tests verify:
- MongoDB connection & ping
- Phone-only customer creation (required field validation)
- Full customer record creation
- Form-data submission
- List & search customer API
- Admin authentication & session security
- Dashboard rendering
- In-memory Excel spreadsheet generation & download

---

## 🛡️ Security Best Practices

1. **Change Default Admin Password**: Update `ADMIN_PASSWORD` in your Render environment variables or `.env`.
2. **Session Security**: Session cookies are signed using `SECRET_KEY`.
3. **MongoDB Connection**: Credentials are encrypted over SSL (`mongodb+srv`). Ensure MongoDB Atlas Network Access has `0.0.0.0/0` (Allow Access from Anywhere) configured so Render servers can connect.
