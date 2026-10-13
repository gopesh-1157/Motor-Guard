import logging
import time
from typing import Optional, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from backend.app.config import settings

logger = logging.getLogger("motorguard.db")


class MongoDBManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    async def connect_to_database(cls) -> None:
        try:
            logger.info("Initializing MongoDB connection to %s", settings.MONGO_URI)
            cls.client = AsyncIOMotorClient(
                settings.MONGO_URI,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000,
            )
            cls.db = cls.client[settings.MONGO_DB_NAME]
            logger.info("Connected to MongoDB database: %s", settings.MONGO_DB_NAME)
        except Exception as e:
            logger.error("Failed to initialize MongoDB client: %s", e)

    @classmethod
    async def close_database_connection(cls) -> None:
        if cls.client:
            logger.info("Closing MongoDB connection pool")
            cls.client.close()
            cls.client = None
            cls.db = None

    @classmethod
    async def ping(cls) -> Tuple[bool, float, Optional[str]]:
        """Pings MongoDB and returns (is_healthy, latency_ms, error_message)."""
        if not cls.client:
            return False, 0.0, "Client not initialized"
        start = time.perf_counter()
        try:
            await cls.client.admin.command("ping")
            latency_ms = (time.perf_counter() - start) * 1000.0
            return True, round(latency_ms, 2), None
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            return False, round(latency_ms, 2), str(exc)


db_manager = MongoDBManager()
