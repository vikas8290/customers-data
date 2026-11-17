import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "customer-portal-secret-key-render-deploy-2024")
    
    # MongoDB
    MONGO_URI: str = os.getenv(
        "MONGO_URI",
        "mongodb+srv://vikashkumawat1007_db_user:uFNj1xDgFM9ONAtp@cluster0.e0tcnaf.mongodb.net/"
    )
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "customer_portal_db")
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "customers")
    
    # Admin Portal Credentials
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    
    # CORS
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]

settings = Settings()
