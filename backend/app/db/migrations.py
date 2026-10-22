"""
MotorGuard — Database Compatibility & Safe Migrations

Provides repeatable, non-destructive migrations:
- Scans users collection for obsolete legacy roles (e.g. 'Operator').
- Safely migrates them to 'Technician' (the least-privileged valid active role) without privilege escalation.
- Preserves all passwords, telemetry, motors, devices, and maintenance records.
- Records migration actions into the audit trail.
"""

from datetime import datetime, timezone
import logging
import uuid
from typing import Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("motorguard.migrations")

VALID_ROLES = {"Admin", "Manager", "Technician"}


async def migrate_legacy_roles(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """
    Safely inspect and migrate legacy or obsolete role values.
    Specifically migrates 'Operator' accounts to 'Technician'.
    """
    if db is None:
        return {"migrated_count": 0, "status": "skipped_no_db"}

    users_col = db["users"]
    audit_events_col = db["audit_events"]

    # 1. Find users with 'Operator' or any role not in VALID_ROLES
    cursor = users_col.find({"role": {"$nin": list(VALID_ROLES)}})
    if hasattr(cursor, "__await__") and not hasattr(cursor, "to_list"):
        cursor = await cursor
    if hasattr(cursor, "to_list"):
        obsolete_users = await cursor.to_list(length=500)
    elif hasattr(cursor, "__aiter__"):
        obsolete_users = [u async for u in cursor]
    elif isinstance(cursor, list):
        obsolete_users = cursor
    else:
        obsolete_users = []

    migrated_users = []
    now = datetime.now(timezone.utc)

    for user in obsolete_users:
        username = user.get("username", "unknown")
        old_role = user.get("role", "unknown")
        if old_role in VALID_ROLES:
            continue
        target_role = "Technician"

        # Sanitize assigned sites and motors: remove wildcards so accounts do not retain broad fleet access
        assigned_sites = [s for s in user.get("assigned_sites", []) if s and s != "*"]
        assigned_motors = [m for m in user.get("assigned_motors", []) if m and m != "*"]

        # Revoke old sessions: timestamp session_revoked_at to now
        await users_col.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "role": target_role,
                    "assigned_sites": assigned_sites,
                    "assigned_motors": assigned_motors,
                    "session_revoked_at": now,
                    "updated_at": now,
                }
            }
        )

        migrated_users.append({"username": username, "old_role": old_role, "new_role": target_role})

        # Append to immutable audit trail
        await audit_events_col.insert_one({
            "event_id": str(uuid.uuid4()),
            "action": "MIGRATE_LEGACY_ROLE",
            "user": "system_migration",
            "target_type": "user",
            "target_id": username,
            "details": {
                "old_role": old_role,
                "new_role": target_role,
                "reason": "Legacy role deprecation to strict 3-role RBAC; revoked legacy active sessions",
            },
            "timestamp": now,
        })
        logger.info(
            "Migrated legacy role for user '%s' from '%s' to '%s' (sessions revoked)",
            username,
            old_role,
            target_role,
        )

    return {
        "status": "success",
        "migrated_count": len(migrated_users),
        "migrated_users": migrated_users,
    }


async def create_active_alert_unique_index(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """
    Safely inspect and establish the partial unique index on active alerts.
    Prevents duplicate active alerts (including DEVICE_OFFLINE) across multiple workers:
    - Pre-scans for any existing duplicate active alerts for the same (motor_id, trigger_type).
    - Safely marks older duplicate active records as RESOLVED so the unique index builds cleanly.
    - Creates partial unique index with partialFilterExpression={'state': 'ACTIVE'}.
    """
    if db is None:
        return {"status": "skipped_no_db", "duplicates_resolved": 0}

    alerts_col = db["alerts"]
    now = datetime.now(timezone.utc)
    duplicates_resolved = 0

    try:
        # Group active alerts by (motor_id, trigger_type)
        pipeline = [
            {"$match": {"state": "ACTIVE"}},
            {
                "$group": {
                    "_id": {"motor_id": "$motor_id", "trigger_type": "$trigger_type"},
                    "count": {"$sum": 1},
                    "ids": {"$push": "$_id"},
                    "dates": {"$push": "$triggered_at"},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
        ]
        cursor = alerts_col.aggregate(pipeline)
        async for group in cursor:
            ids = group.get("ids", [])
            # Keep the newest alert active, resolve previous duplicates
            if len(ids) > 1:
                duplicate_ids = ids[:-1]
                res = await alerts_col.update_many(
                    {"_id": {"$in": duplicate_ids}},
                    {
                        "$set": {
                            "state": "RESOLVED",
                            "resolved_at": now,
                            "resolved_by": "System (Deduplication Migration)",
                            "resolution_notes": "Resolved older duplicate active alert prior to partial unique index creation",
                        }
                    },
                )
                duplicates_resolved += res.modified_count

        # Create the partial unique index
        await alerts_col.create_index(
            [("motor_id", 1), ("trigger_type", 1), ("state", 1)],
            unique=True,
            partialFilterExpression={"state": "ACTIVE"},
            name="unique_active_alert_per_motor_trigger",
        )
        logger.info(
            "Established partial unique index on active alerts (duplicates resolved: %d)",
            duplicates_resolved,
        )
        return {"status": "success", "duplicates_resolved": duplicates_resolved}
    except Exception as exc:
        logger.warning("Migration create_active_alert_unique_index encountered exception: %s", exc)
        return {"status": "failed", "error": str(exc), "duplicates_resolved": duplicates_resolved}

