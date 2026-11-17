from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import db_manager
from app.routers import api, portal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to MongoDB Atlas
    logger.info("Initializing application and connecting to MongoDB...")
    db_manager.connect()
    yield
    # Shutdown: Clean up connections
    logger.info("Shutting down application...")
    db_manager.close()

app = FastAPI(
    title="Customer Data Hub & Portal",
    description="Customer data collection API, MongoDB storage, Admin Portal, and Excel Export. Deployable on Render.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware (Allows any website to submit customer data to /api/customers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session Middleware for Admin Portal authentication
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="customer_hub_admin_session",
    max_age=86400 * 7,  # 7 days
    same_site="lax",
    https_only=False,  # Set True in strict production HTTPS if behind SSL proxy
)

# Mount static files directory if present
BASE_DIR = Path(__file__).resolve().parent
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include Routers
app.include_router(portal.router)
app.include_router(api.router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception occurred: {exc}", exc_info=True)
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Internal server error", "detail": str(exc)},
        )
    # For portal web pages
    return JSONResponse(
        status_code=500,
        content={"error": "An internal server error occurred. Please contact the administrator."},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
