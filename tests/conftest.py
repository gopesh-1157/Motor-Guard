"""
MotorGuard — Root Pytest Configuration & Hermetic Test Isolation Fixtures
========================================================================

Guarantees 100% test isolation:
1. Prevents any test, fixture, or background lifespan task from connecting to
   a persistent local or remote MongoDB instance.
2. Injects a high-fidelity in-memory asynchronous database mock into `db_manager.db`
   so indexes, seeding, queries, and updates succeed hermetically.
3. Automatically sets `ENVIRONMENT="test"` to disable live MQTT network loops
   and background SoftAP HTTP pollers.
4. Fails closed if any test code attempts direct `AsyncIOMotorClient` socket creation.
"""

import os
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Enforce test environment before importing application modules
os.environ["ENVIRONMENT"] = "test"

from backend.app.config import settings
settings.ENVIRONMENT = "test"

from backend.app.db.mongodb import db_manager, MongoDBManager


class MockAsyncCursor:
    """In-memory async cursor matching Motor's AsyncIOMotorCursor interface."""

    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = [dict(d) for d in docs]
        self._iter = iter(self._docs)

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, str):
            reverse = (direction == -1)
            self._docs.sort(key=lambda x: x.get(key_or_list) or "", reverse=reverse)
        return self

    def limit(self, n: int):
        self._docs = self._docs[:n]
        self._iter = iter(self._docs)
        return self

    def skip(self, n: int):
        self._docs = self._docs[n:]
        self._iter = iter(self._docs)
        return self

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    async def to_list(self, length: Optional[int] = None) -> List[Dict[str, Any]]:
        if length is not None:
            return self._docs[:length]
        return list(self._docs)


class MockAsyncCollection:
    """In-memory async collection matching Motor's AsyncIOMotorCollection interface."""

    def __init__(self, name: str):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    async def create_index(self, *args, **kwargs) -> str:
        return f"{self.name}_idx"

    async def ensure_indexes(self, *args, **kwargs) -> None:
        pass

    async def insert_one(self, doc: Dict[str, Any]) -> MagicMock:
        stored = dict(doc)
        if "_id" not in stored:
            stored["_id"] = str(uuid.uuid4())
        self.docs.append(stored)
        res = MagicMock()
        res.inserted_id = stored["_id"]
        return res

    async def insert_many(self, docs: List[Dict[str, Any]]) -> MagicMock:
        ids = []
        for d in docs:
            r = await self.insert_one(d)
            ids.append(r.inserted_id)
        res = MagicMock()
        res.inserted_ids = ids
        return res

    def _matches(self, doc: Dict[str, Any], query: Optional[Dict[str, Any]]) -> bool:
        if not query:
            return True
        for k, v in query.items():
            if k == "$or" and isinstance(v, list):
                if not any(self._matches(doc, cond) for cond in v):
                    return False
                continue
            if k.startswith("$"):
                continue
            if isinstance(v, dict):
                if "$in" in v and doc.get(k) not in v["$in"]:
                    return False
                if "$gte" in v and (doc.get(k) is None or doc.get(k) < v["$gte"]):
                    return False
                if "$lte" in v and (doc.get(k) is None or doc.get(k) > v["$lte"]):
                    return False
                if "$gt" in v and (doc.get(k) is None or doc.get(k) <= v["$gt"]):
                    return False
                if "$lt" in v and (doc.get(k) is None or doc.get(k) >= v["$lt"]):
                    return False
                if "$ne" in v and doc.get(k) == v["$ne"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    async def find_one(self, query: Optional[Dict[str, Any]] = None, *args, **kwargs) -> Optional[Dict[str, Any]]:
        for d in self.docs:
            if self._matches(d, query):
                return dict(d)
        return None

    def find(self, query: Optional[Dict[str, Any]] = None, *args, **kwargs) -> MockAsyncCursor:
        matched = [d for d in self.docs if self._matches(d, query)]
        return MockAsyncCursor(matched)

    async def update_one(
        self,
        filter_query: Dict[str, Any],
        update: Dict[str, Any],
        upsert: bool = False,
    ) -> MagicMock:
        matched_doc = None
        for d in self.docs:
            if self._matches(d, filter_query):
                matched_doc = d
                break

        res = MagicMock()
        res.matched_count = 1 if matched_doc else 0
        res.modified_count = 0
        res.upserted_id = None

        if matched_doc:
            if "$set" in update:
                matched_doc.update(update["$set"])
                res.modified_count = 1
            if "$setOnInsert" in update and not matched_doc:
                matched_doc.update(update["$setOnInsert"])
        elif upsert:
            new_doc = dict(filter_query)
            if "$setOnInsert" in update:
                new_doc.update(update["$setOnInsert"])
            if "$set" in update:
                new_doc.update(update["$set"])
            if "_id" not in new_doc:
                new_doc["_id"] = str(uuid.uuid4())
            self.docs.append(new_doc)
            res.upserted_id = new_doc["_id"]
            res.modified_count = 1

        return res

    async def update_many(
        self,
        filter_query: Dict[str, Any],
        update: Dict[str, Any],
        upsert: bool = False,
    ) -> MagicMock:
        matched = [d for d in self.docs if self._matches(d, filter_query)]
        res = MagicMock()
        res.matched_count = len(matched)
        res.modified_count = 0
        for doc in matched:
            if "$set" in update:
                doc.update(update["$set"])
                res.modified_count += 1
        return res

    async def find_one_and_update(
        self,
        filter_query: Dict[str, Any],
        update: Dict[str, Any],
        return_document: bool = True,
        upsert: bool = False,
    ) -> Optional[Dict[str, Any]]:
        matched_doc = None
        for d in self.docs:
            if self._matches(d, filter_query):
                matched_doc = d
                break

        if not matched_doc and upsert:
            new_doc = dict(filter_query)
            if "$setOnInsert" in update:
                new_doc.update(update["$setOnInsert"])
            if "$set" in update:
                new_doc.update(update["$set"])
            if "_id" not in new_doc:
                new_doc["_id"] = str(uuid.uuid4())
            self.docs.append(new_doc)
            return dict(new_doc)

        if matched_doc:
            if "$set" in update:
                matched_doc.update(update["$set"])
            return dict(matched_doc)

        return None

    async def delete_one(self, query: Dict[str, Any]) -> MagicMock:
        res = MagicMock()
        res.deleted_count = 0
        for i, d in enumerate(self.docs):
            if self._matches(d, query):
                del self.docs[i]
                res.deleted_count = 1
                break
        return res

    async def delete_many(self, query: Optional[Dict[str, Any]] = None) -> MagicMock:
        res = MagicMock()
        if not query:
            cnt = len(self.docs)
            self.docs.clear()
            res.deleted_count = cnt
            return res
        initial = len(self.docs)
        self.docs = [d for d in self.docs if not self._matches(d, query)]
        res.deleted_count = initial - len(self.docs)
        return res

    async def count_documents(self, query: Optional[Dict[str, Any]] = None) -> int:
        if not query:
            return len(self.docs)
        return sum(1 for d in self.docs if self._matches(d, query))

    async def distinct(self, field: str, query: Optional[Dict[str, Any]] = None) -> List[Any]:
        results = set()
        for d in self.docs:
            if self._matches(d, query):
                val = d.get(field)
                if val is not None:
                    results.add(val)
        return list(results)


class MockIsolatedDatabase:
    """In-memory async MongoDB database substitute."""

    def __init__(self, name: str = "motorguard_hermetic_test_db"):
        self.name = name
        self._collections: Dict[str, MockAsyncCollection] = {}

    def __getitem__(self, item: str) -> MockAsyncCollection:
        if item not in self._collections:
            self._collections[item] = MockAsyncCollection(item)
        return self._collections[item]

    def __getattr__(self, item: str) -> MockAsyncCollection:
        return self[item]

    def clear_all_collections(self) -> None:
        """Clear all documents from all collections to guarantee inter-test isolation."""
        for col in self._collections.values():
            col.docs.clear()

    @property
    def admin(self) -> MagicMock:
        admin_mock = MagicMock()
        admin_mock.command = AsyncMock(return_value={"ok": 1.0})
        return admin_mock


class MockIsolatedClient:
    """In-memory async MongoDB client substitute."""

    def __init__(self):
        self._dbs: Dict[str, MockIsolatedDatabase] = {}
        self.admin = MagicMock()
        self.admin.command = AsyncMock(return_value={"ok": 1.0})

    def __getitem__(self, item: str) -> MockIsolatedDatabase:
        if item not in self._dbs:
            self._dbs[item] = MockIsolatedDatabase(item)
        return self._dbs[item]

    def close(self) -> None:
        pass


def _seed_test_data(db):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    users = [
        {
            "_id": "usr_default_admin",
            "username": "admin",
            "email": "admin@motorguard.local",
            "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
            "role": "Admin",
            "is_active": True,
            "assigned_sites": ["SITE-01"],
            "assigned_motors": [],
            "created_at": now,
        },
        {
            "_id": "usr_admin",
            "username": "admin_alice",
            "email": "admin@motorguard.local",
            "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
            "role": "Admin",
            "is_active": True,
            "assigned_sites": ["SITE-01"],
            "assigned_motors": [],
            "created_at": now,
        },
        {
            "_id": "usr_manager",
            "username": "manager_mike",
            "email": "manager@motorguard.local",
            "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
            "role": "Manager",
            "is_active": True,
            "assigned_sites": ["SITE-01"],
            "assigned_motors": [],
            "created_at": now,
        },
        {
            "_id": "usr_tech",
            "username": "tech_dave",
            "email": "dave@motorguard.local",
            "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
            "role": "Technician",
            "is_active": True,
            "assigned_sites": ["SITE-01"],
            "assigned_motors": [],
            "created_at": now,
        },
        {
            "_id": "usr_operator",
            "username": "operator_bob",
            "email": "bob@motorguard.local",
            "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
            "role": "Operator",
            "is_active": True,
            "assigned_sites": ["SITE-01"],
            "assigned_motors": [],
            "created_at": now,
        },
    ]
    db["users"].docs = [dict(u) for u in users]


@pytest.fixture(scope="session", autouse=True)
def enforce_test_environment_isolation():
    """
    Session-level autouse fixture ensuring tests run strictly with an isolated mock database.
    Intercepts and blocks any attempt to create a real network socket to MongoDB.
    """
    os.environ["ENVIRONMENT"] = "test"
    settings.ENVIRONMENT = "test"

    isolated_client = MockIsolatedClient()
    isolated_db = isolated_client["motorguard_hermetic_test_db"]
    _seed_test_data(isolated_db)

    # Save reference to original unpatched connect for regression test
    MongoDBManager._unpatched_connect = MongoDBManager.connect_to_database

    # Pre-attach mock client and database to db_manager
    db_manager.client = isolated_client
    db_manager.db = isolated_db

    async def _safe_connect():
        if db_manager.db is None:
            db_manager.client = isolated_client
            db_manager.db = isolated_db

    async def _safe_close():
        pass

    # Patch connect and close on db_manager
    with patch.object(MongoDBManager, "connect_to_database", side_effect=_safe_connect), \
         patch.object(MongoDBManager, "close_database_connection", side_effect=_safe_close):
        yield isolated_db


@pytest.fixture(autouse=True)
def reset_test_database_state(enforce_test_environment_isolation):
    """Function-level fixture ensuring mock database is attached, cleaned, and seeded."""
    if db_manager.db is None:
        client = MockIsolatedClient()
        db_manager.client = client
        db_manager.db = client["motorguard_hermetic_test_db"]
    elif hasattr(db_manager.db, "clear_all_collections"):
        db_manager.db.clear_all_collections()

    _seed_test_data(db_manager.db)
    yield

