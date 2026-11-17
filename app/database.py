import logging
import certifi
from pymongo import MongoClient, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from app.config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    client: MongoClient | None = None
    db: Database | None = None

    def connect(self):
        if self.client is None:
            logger.info("Connecting to MongoDB Atlas...")
            try:
                self.client = MongoClient(
                    settings.MONGO_URI,
                    tlsCAFile=certifi.where(),
                    serverSelectionTimeoutMS=7000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=15000,
                )
                self.db = self.client[settings.DATABASE_NAME]
                # Test connection and create indexes
                self._ensure_indexes()
                logger.info(f"Connected to MongoDB database: {settings.DATABASE_NAME}")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB Atlas: {e}")
                raise

    def _ensure_indexes(self):
        try:
            # Customers collection indexes
            cust_col = self.get_customers_collection()
            cust_col.create_index([("created_at", DESCENDING)])
            cust_col.create_index([("phone", 1)])
            cust_col.create_index([("from", 1)])

            # Users collection indexes
            users_col = self.get_users_collection()
            users_col.create_index([("api_key", 1)], unique=True)
            users_col.create_index([("username", 1)])
        except Exception as e:
            logger.warning(f"Could not create MongoDB indexes: {e}")

    def get_database(self) -> Database:
        if self.db is None:
            self.connect()
        return self.db

    def get_customers_collection(self) -> Collection:
        return self.get_database()[settings.COLLECTION_NAME]

    def get_users_collection(self) -> Collection:
        return self.get_database()["users"]

    def ping(self) -> bool:
        try:
            if self.client is None:
                self.connect()
            self.client.admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            return False

    def close(self):
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB connection closed.")

db_manager = DatabaseManager()

def get_db() -> Database:
    return db_manager.get_database()

def get_customers_collection() -> Collection:
    return db_manager.get_customers_collection()

def get_users_collection() -> Collection:
    return db_manager.get_users_collection()
