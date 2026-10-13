"""
MotorGuard — User Database Service

Manages persistence, indexes, and queries for the 'users' collection in MongoDB.
"""

from datetime import datetime, timezone
import logging
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.schemas.user import UserCreate, UserOut, UserInDB
from backend.app.core.security import get_password_hash, verify_password

logger = logging.getLogger("motorguard.user_service")


class UserService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["users"]

    async def ensure_indexes(self) -> None:
        """Create unique indexes on username and email."""
        await self.collection.create_index("username", unique=True)
        await self.collection.create_index("email", unique=True)
        logger.info("Users collection indexes verified")

    async def get_by_username(self, username: str) -> Optional[UserInDB]:
        """Fetch user document by username."""
        doc = await self.collection.find_one({"username": username})
        if not doc:
            return None
        doc["id"] = str(doc.pop("_id", ""))
        return UserInDB(**doc)

    async def get_by_id(self, user_id: str) -> Optional[UserOut]:
        """Fetch user by id."""
        from bson import ObjectId
        try:
            oid = ObjectId(user_id)
        except Exception:
            return None
        doc = await self.collection.find_one({"_id": oid})
        if not doc:
            return None
        doc["id"] = str(doc.pop("_id", ""))
        return UserOut(**doc)

    async def create_user(self, user_in: UserCreate) -> UserOut:
        """Hash password and insert a new user document."""
        now = datetime.now(timezone.utc)
        doc = user_in.model_dump(exclude={"password"})
        doc["password_hash"] = get_password_hash(user_in.password)
        doc["created_at"] = now
        doc["last_login_at"] = None

        result = await self.collection.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        return UserOut(**doc)

    async def authenticate(self, username: str, password: str) -> Optional[UserInDB]:
        """Verify username and password, update last_login_at if valid."""
        user = await self.get_by_username(username)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            return None

        # Update last login
        now = datetime.now(timezone.utc)
        from bson import ObjectId
        try:
            await self.collection.update_one(
                {"username": username},
                {"$set": {"last_login_at": now}}
            )
            user.last_login_at = now
        except Exception as e:
            logger.warning("Could not update last_login_at for %s: %s", username, e)

        return user

    async def list_users(self, skip: int = 0, limit: int = 50) -> List[UserOut]:
        """List active/registered users."""
        cursor = self.collection.find({}).skip(skip).limit(limit)
        users = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id", ""))
            users.append(UserOut(**doc))
        return users

    async def seed_default_admin(self) -> None:
        """Create default admin user if users collection is empty."""
        count = await self.collection.count_documents({})
        if count == 0:
            logger.info("No users found. Seeding default Admin user...")
            admin_user = UserCreate(
                username="admin",
                email="admin@motorguard.local",
                role="Admin",
                password="adminpassword123",
                assigned_sites=["SITE-MAIN"],
                assigned_motors=[],
                is_active=True,
            )
            await self.create_user(admin_user)
            logger.info("Default Admin user 'admin' seeded")
