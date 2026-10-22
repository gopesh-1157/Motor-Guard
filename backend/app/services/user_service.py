"""
MotorGuard — User Database Service

Manages persistence, indexes, and queries for the 'users' collection in MongoDB.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.schemas.user import UserCreate, UserUpdate, UserOut, UserInDB
from backend.app.core.security import get_password_hash, verify_password

logger = logging.getLogger("motorguard.user_service")


class UserService:
    _admin_lock = asyncio.Lock()

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["users"]
        self.audit_collection = db["audit_events"]
        self.audit_logs_col = db["audit_logs"]

    async def _audit(self, action: str, user: str, target_id: str, details: dict) -> None:
        """Record administrative action into immutable audit trails."""
        now = datetime.now(timezone.utc)
        import uuid
        event_doc = {
            "event_id": str(uuid.uuid4()),
            "action": action,
            "user": user,
            "target_type": "user",
            "target_id": target_id,
            "details": details,
            "timestamp": now,
        }
        await self.audit_collection.insert_one(event_doc)

        log_doc = {
            "audit_id": f"AUD-{uuid.uuid4().hex[:10].upper()}",
            "timestamp": now,
            "actor": user,
            "action": action,
            "entity_type": "user",
            "entity_id": target_id,
            "details": details,
        }
        await self.audit_logs_col.insert_one(log_doc)

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

    async def get_by_email(self, email: str) -> Optional[UserInDB]:
        """Fetch user document by email."""
        doc = await self.collection.find_one({"email": email})
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

    async def create_user(self, user_in: UserCreate, actor: Optional[str] = None) -> UserOut:
        """Hash password and insert a new user document."""
        from fastapi import HTTPException, status
        # Check email uniqueness before insertion
        existing_email = await self.collection.find_one({"email": user_in.email})
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{user_in.email}' is already registered",
            )

        if user_in.role == "Manager":
            from backend.app.config import settings
            if settings.ENVIRONMENT.strip().lower() == "production" and not user_in.assigned_sites:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="In production, Managers must be explicitly assigned to at least one site scope. Unscoped Managers are prohibited.",
                )

        now = datetime.now(timezone.utc)
        doc = user_in.model_dump(exclude={"password"})
        doc["password_hash"] = get_password_hash(user_in.password)
        doc["created_at"] = now
        doc["last_login_at"] = None

        result = await self.collection.insert_one(doc)
        doc["id"] = str(result.inserted_id)

        actor_name = actor or "system_bootstrap"
        await self._audit(
            action="CREATE_USER",
            user=actor_name,
            target_id=user_in.username,
            details={
                "role": user_in.role,
                "email": user_in.email,
                "assigned_sites": user_in.assigned_sites,
                "assigned_motors": user_in.assigned_motors,
            },
        )
        return UserOut(**doc)

    async def authenticate(self, username: str, password: str) -> Optional[UserInDB]:
        """Verify username and password, update last_login_at if valid."""
        user = await self.get_by_username(username)
        if not user:
            return None

        password_valid = verify_password(password, user.password_hash)

        # Allow seamless compatibility for default admin account in development:
        # Accepts either 'adminpassword123' (README/modal standard) or 'admin123' (legacy demo seed).
        if not password_valid and user.username == "admin":
            from backend.app.config import settings
            if settings.ENVIRONMENT.strip().lower() != "production":
                if password in ("adminpassword123", "admin123"):
                    if verify_password("admin123", user.password_hash) or verify_password("adminpassword123", user.password_hash):
                        password_valid = True
                        if password == "adminpassword123":
                            try:
                                new_hash = get_password_hash("adminpassword123")
                                await self.collection.update_one(
                                    {"username": "admin"},
                                    {"$set": {"password_hash": new_hash}}
                                )
                                user.password_hash = new_hash
                            except Exception as ex:
                                logger.warning("Could not migrate admin password hash: %s", ex)

        if not password_valid:
            return None
        if not user.is_active:
            return None

        # Update last login
        now = datetime.now(timezone.utc)
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

    async def list_technicians(self, site_id: Optional[str] = None) -> List[UserOut]:
        """List active users with 'Technician' role for work order assignment."""
        query: dict = {"role": "Technician", "is_active": True}
        if site_id:
            query["$or"] = [
                {"assigned_sites": site_id},
                {"assigned_sites": []},
                {"assigned_sites": {"$exists": False}},
            ]
        cursor = self.collection.find(query)
        technicians = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id", ""))
            technicians.append(UserOut(**doc))
        return technicians

    async def update_user(self, user_id: str, data: "UserUpdate", actor: str) -> UserOut:
        """Update user profile fields, role, site/motor scopes, or activation status atomically."""
        from bson import ObjectId
        from fastapi import HTTPException, status
        try:
            oid = ObjectId(user_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")

        async with self._admin_lock:
            existing = await self.collection.find_one({"_id": oid})
            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")

            # 1. Prevent elevating role to Admin via standard user management
            if data.role == "Admin" and existing.get("role") != "Admin":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Elevating account to Admin is prohibited through user management APIs. Use administrative bootstrap.",
                )

            # 2. Final active Admin protection: cannot deactivate or demote final active Admin
            is_existing_active_admin = (existing.get("role") == "Admin" and existing.get("is_active", True))
            is_being_deactivated = (data.is_active is False)
            is_being_demoted = (data.role is not None and data.role != "Admin")

            if is_existing_active_admin and (is_being_deactivated or is_being_demoted):
                active_admin_count = await self.collection.count_documents({"role": "Admin", "is_active": True})
                if active_admin_count <= 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot deactivate or demote the final active Admin account.",
                    )

            # 3. Check email uniqueness if email is changed
            if data.email and data.email != existing.get("email"):
                duplicate_email = await self.collection.find_one({"email": data.email, "_id": {"$ne": oid}})
                if duplicate_email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Email '{data.email}' is already registered",
                    )

            target_role = data.role or existing.get("role")
            target_sites = data.assigned_sites if data.assigned_sites is not None else existing.get("assigned_sites", [])
            if target_role == "Manager":
                from backend.app.config import settings
                if settings.ENVIRONMENT.strip().lower() == "production" and not target_sites:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="In production, Managers must be explicitly assigned to at least one site scope. Unscoped Managers are prohibited.",
                    )

            now = datetime.now(timezone.utc)
            update_fields = {}
            if data.email is not None:
                update_fields["email"] = data.email
            if data.role is not None:
                update_fields["role"] = data.role
            if data.assigned_sites is not None:
                update_fields["assigned_sites"] = data.assigned_sites
            if data.assigned_motors is not None:
                update_fields["assigned_motors"] = data.assigned_motors
            if data.is_active is not None:
                update_fields["is_active"] = data.is_active
                if data.is_active is False:
                    # Deactivation immediately revokes existing active sessions
                    update_fields["session_revoked_at"] = now
            if data.password is not None:
                update_fields["password_hash"] = get_password_hash(data.password)
                update_fields["session_revoked_at"] = now

            update_fields["updated_at"] = now

            await self.collection.update_one({"_id": oid}, {"$set": update_fields})

            updated_doc = await self.collection.find_one({"_id": oid})
            updated_doc["id"] = str(updated_doc.pop("_id", ""))

            await self._audit(
                action="UPDATE_USER",
                user=actor,
                target_id=existing.get("username", user_id),
                details={
                    "updated_fields": list(update_fields.keys()),
                    "is_active": updated_doc.get("is_active"),
                    "role": updated_doc.get("role"),
                },
            )
            return UserOut(**updated_doc)

    async def delete_user(self, user_id: str, actor: str) -> bool:
        """Safely delete a user account, preserving final active Admin atomically."""
        from bson import ObjectId
        from fastapi import HTTPException, status
        try:
            oid = ObjectId(user_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")

        async with self._admin_lock:
            existing = await self.collection.find_one({"_id": oid})
            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")

            if existing.get("role") == "Admin" and existing.get("is_active", True):
                active_admin_count = await self.collection.count_documents({"role": "Admin", "is_active": True})
                if active_admin_count <= 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot delete the final active Admin account.",
                    )

            await self.collection.delete_one({"_id": oid})
            await self._audit(
                action="DELETE_USER",
                user=actor,
                target_id=existing.get("username", user_id),
                details={"deleted_role": existing.get("role")},
            )
            return True

    async def seed_default_admin(self) -> None:
        """Create default admin user if users collection is empty."""
        count = await self.collection.count_documents({})
        if count == 0:
            from backend.app.config import settings

            if settings.ENVIRONMENT.strip().lower() == "production" and not settings.ADMIN_INITIAL_PASSWORD:
                logger.critical(
                    "FATAL SECURITY VIOLATION: Attempted to seed default admin in production without ADMIN_INITIAL_PASSWORD configured! "
                    "Insecure default password fallback is strictly prohibited in production."
                )
                raise RuntimeError(
                    "Production startup aborted: ADMIN_INITIAL_PASSWORD environment variable is required to seed the initial Admin account."
                )

            admin_pwd = settings.ADMIN_INITIAL_PASSWORD or "adminpassword123"
            logger.info("No users found. Seeding initial Admin user...")
            admin_user = UserCreate(
                username="admin",
                email="admin@motorguard.local",
                role="Admin",
                password=admin_pwd,
                assigned_sites=["SITE-MAIN"],
                assigned_motors=[],
                is_active=True,
            )
            await self.create_user(admin_user)
            logger.info("Default Admin user 'admin' seeded")

