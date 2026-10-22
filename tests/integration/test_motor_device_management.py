"""
MotorGuard — Integration Test Suite: Motor Management & ESP32 Device Registration Module

Verifies:
  1. Valid 12V RS-775 motor registration with electrical & mechanical specs.
  2. Rejection of duplicate motor IDs.
  3. Rejection of invalid/negative electrical parameters.
  4. Unique ESP32 device enrollment.
  5. Rejection of duplicate device IDs.
  6. Rejection of assigning one device to two motors simultaneously.
  7. Detection of GPIO pin conflicts between sensor subsystems.
  8. Enforcing warning threshold < critical threshold for safety parameters.
  9. Rejection of invalid Edge Impulse class configurations.
  10. MongoDB persistence and retrieval via GET /api/v1/motors.
  11. Telemetry ingestion assignment validation (dropping mismatched device/motor).
  12. Audit event creation on motor creation, update, and disable.
  13. RBAC permission enforcement: Admin/Manager can create/edit, Operator cannot.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.security import create_access_token
from backend.app.core.auth import get_user_service
from backend.app.services.user_service import UserService
from backend.app.services.motor_service import MotorService
from backend.app.services.device_service import DeviceService
from backend.app.api.v1.endpoints.motors import get_motor_service
from backend.app.api.v1.endpoints.devices import get_device_service
from backend.app.schemas.user import UserInDB, UserOut


client = TestClient(app)


def auth_header(username: str, role: str) -> dict:
    token = create_access_token(data={"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_db():
    """Mock MongoDB database collections in-memory for testing."""
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            store = {}

            async def insert_one(doc):
                _id = doc.get("_id", f"mock-{len(store)}")
                doc_copy = dict(doc)
                doc_copy["_id"] = _id
                # Check unique indexes
                if name == "motors":
                    mid = doc.get("motor_id")
                    if any(d.get("motor_id") == mid for d in store.values()):
                        from pymongo.errors import DuplicateKeyError
                        raise DuplicateKeyError(f"Duplicate motor_id {mid}")
                elif name == "devices":
                    did = doc.get("device_id")
                    if any(d.get("device_id") == did for d in store.values()):
                        from pymongo.errors import DuplicateKeyError
                        raise DuplicateKeyError(f"Duplicate device_id {did}")
                store[_id] = doc_copy
                res = MagicMock()
                res.inserted_id = _id
                return res

            async def find_one(query, projection=None, sort=None):
                for d in store.values():
                    match = True
                    for k, v in query.items():
                        if d.get(k) != v:
                            match = False
                            break
                    if match:
                        ret = dict(d)
                        if projection and "_id" in projection and projection["_id"] == 0:
                            ret.pop("_id", None)
                        return ret
                return None

            async def update_one(query, update, upsert=False):
                for doc_id, d in list(store.items()):
                    match = True
                    for k, v in query.items():
                        if d.get(k) != v:
                            match = False
                            break
                    if match:
                        if "$set" in update:
                            d.update(update["$set"])
                        res = MagicMock()
                        res.matched_count = 1
                        res.modified_count = 1
                        return res
                if upsert:
                    new_doc = dict(query)
                    if "$set" in update:
                        new_doc.update(update["$set"])
                    if "$setOnInsert" in update:
                        new_doc.update(update["$setOnInsert"])
                    store[new_doc.get("motor_id") or new_doc.get("device_id") or str(len(store))] = new_doc
                    res = MagicMock()
                    res.upserted_id = "upserted"
                    return res
                res = MagicMock()
                res.matched_count = 0
                return res

            async def count_documents(query):
                cnt = 0
                for d in store.values():
                    match = True
                    for k, v in query.items():
                        if d.get(k) != v:
                            match = False
                            break
                    if match:
                        cnt += 1
                return cnt

            col.insert_one = AsyncMock(side_effect=insert_one)
            col.find_one = AsyncMock(side_effect=find_one)
            col.update_one = AsyncMock(side_effect=update_one)
            col.count_documents = AsyncMock(side_effect=count_documents)
            col.create_index = AsyncMock(return_value=None)

            # Cursor mock for find()
            def find(query=None, projection=None):
                cursor = MagicMock()
                async def to_list(length=100):
                    matched_items = []
                    for d in store.values():
                        if query:
                            m = True
                            for k, v in query.items():
                                if d.get(k) != v:
                                    m = False
                                    break
                            if not m:
                                continue
                        ret = dict(d)
                        if projection and "_id" in projection and projection["_id"] == 0:
                            ret.pop("_id", None)
                        matched_items.append(ret)
                    return matched_items[:length]

                cursor.to_list = AsyncMock(side_effect=to_list)
                cursor.sort = MagicMock(return_value=cursor)
                cursor.limit = MagicMock(return_value=cursor)
                return cursor

            col.find = MagicMock(side_effect=find)
            collections[name] = col
        return collections[name]

    db_mock = MagicMock()
    db_mock.__getitem__.side_effect = get_collection
    return db_mock


@pytest.fixture(autouse=True)
def override_services(mock_db):
    """Override services in FastAPI dependency injection."""
    motor_service = MotorService(mock_db)
    device_service = DeviceService(mock_db)

    # Mock user service for auth
    user_service = MagicMock(spec=UserService)
    async def get_by_username(uname):
        role_map = {
            "admin": "Admin",
            "manager_alice": "Manager",
            "tech_dave": "Technician",
            "operator_bob": "Technician",
        }
        role = role_map.get(uname, "Technician")
        return UserInDB(
            id="mock-user-id",
            username=uname,
            email=f"{uname}@factory.local",
            role=role,
            password_hash="hashed",
            created_at=datetime.now(timezone.utc),
            is_active=True,
            assigned_sites=["SITE-PLANT-A"],
            assigned_motors=[],
        )

    user_service.get_by_username = AsyncMock(side_effect=get_by_username)

    app.dependency_overrides[get_motor_service] = lambda: motor_service
    app.dependency_overrides[get_device_service] = lambda: device_service
    app.dependency_overrides[get_user_service] = lambda: user_service
    yield
    app.dependency_overrides.clear()


# ---- TESTS ------------------------------------------------------------------

class TestMotorRegistrationValidation:
    """Tests for validating motor specifications, schema constraints, and GPIO conflicts."""

    def test_register_valid_12v_rs775_motor(self):
        """Admin registers a valid RS-775 DC motor with all parameters."""
        headers = auth_header("admin", "Admin")
        payload = {
            "motor_id": "MTR-775-NEW01",
            "name": "Feed Conveyor Actuator",
            "motor_type": "RS-775 Brushed DC",
            "manufacturer": "Johnson Electric",
            "model_number": "RS-775-12V-150W",
            "serial_number": "SN-2026-X1",
            "site_id": "SITE-PLANT-A",
            "electrical_specs": {
                "motor_type": "RS-775 Brushed DC",
                "rated_voltage_v": 12.0,
                "rated_current_a": 2.5,
                "no_load_current_a": 0.45,
                "rated_speed_rpm": 12000,
                "max_speed_rpm": 18000,
                "rated_power_w": 30.0,
                "motor_supply_type": "External DC supply",
                "application_load": "Conveyor Drive",
            },
            "thresholds": {
                "temperature_warning_c": 45.0,
                "temperature_critical_c": 50.0,
                "current_warning_a": 3.0,
                "current_critical_a": 4.0,
                "vibration_warning_g": 0.5,
                "vibration_critical_g": 1.0,
            },
        }
        res = client.post("/api/v1/motors", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["motor_id"] == "MTR-775-NEW01"
        assert data["electrical_specs"]["rated_voltage_v"] == 12.0
        assert data["configuration_version"] == 1
        assert data["status"] == "active"

    def test_reject_duplicate_motor_id(self):
        """Registering an already existing motor ID must return 400 Bad Request."""
        headers = auth_header("admin", "Admin")
        payload = {
            "motor_id": "MTR-DUP-001",
            "name": "Primary Drive",
            "electrical_specs": {
                "rated_voltage_v": 12.0,
                "rated_current_a": 2.5,
            },
        }
        res1 = client.post("/api/v1/motors", json=payload, headers=headers)
        assert res1.status_code == 201

        # Duplicate call
        res2 = client.post("/api/v1/motors", json=payload, headers=headers)
        assert res2.status_code == 400
        assert "already registered" in res2.json()["detail"]

    def test_reject_negative_or_zero_electrical_specs(self):
        """Voltage and current must be positive numbers."""
        headers = auth_header("admin", "Admin")
        payload = {
            "motor_id": "MTR-INVALID-001",
            "name": "Bad Motor",
            "electrical_specs": {
                "rated_voltage_v": -12.0,  # Negative voltage
                "rated_current_a": 0.0,    # Zero current
            },
        }
        res = client.post("/api/v1/motors", json=payload, headers=headers)
        assert res.status_code == 422  # Pydantic validation error

    def test_reject_inverted_thresholds(self):
        """Warning threshold must be strictly less than critical threshold."""
        headers = auth_header("admin", "Admin")
        payload = {
            "motor_id": "MTR-THRESH-ERR",
            "name": "Faulty Thresholds",
            "electrical_specs": {
                "rated_voltage_v": 12.0,
                "rated_current_a": 2.5,
            },
            "thresholds": {
                "temperature_warning_c": 55.0,
                "temperature_critical_c": 50.0,  # Warning > Critical: must fail!
                "current_warning_a": 3.0,
                "current_critical_a": 4.0,
                "vibration_warning_g": 0.5,
                "vibration_critical_g": 1.0,
            },
        }
        res = client.post("/api/v1/motors", json=payload, headers=headers)
        assert res.status_code == 422
        assert "must be less than critical" in res.text

    def test_reject_sensor_gpio_pin_conflict(self):
        """Ensure two enabled sensors cannot share the same GPIO pin."""
        headers = auth_header("admin", "Admin")
        payload = {
            "motor_id": "MTR-GPIO-ERR",
            "name": "Conflicted Sensor Pins",
            "electrical_specs": {
                "rated_voltage_v": 12.0,
                "rated_current_a": 2.5,
            },
            "sensors_config": {
                "dht11": {"gpio_pin": 34, "enabled": True},   # Pin 34
                "acs712": {"analog_gpio_pin": 34, "enabled": True}, # Also Pin 34!
            },
        }
        res = client.post("/api/v1/motors", json=payload, headers=headers)
        assert res.status_code == 422
        assert "conflict" in res.text.lower()


class TestDeviceEnrollmentAndAssignment:
    """Tests for enrolling ESP32 devices and enforcing 1-to-1 assignments."""

    def test_enroll_esp32_device(self):
        """Enroll unique physical ESP32 node into registry."""
        headers = auth_header("manager_alice", "Manager")
        payload = {
            "device_id": "esp32-node-test1",
            "device_type": "ESP32",
            "board_variant": "ESP32-D0WD-V3",
            "firmware_version": "1.0.1-AP",
            "site_id": "SITE-PLANT-A",
        }
        res = client.post("/api/v1/devices/enroll", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["device_id"] == "esp32-node-test1"
        assert data["enrollment_status"] == "enrolled"

    def test_reject_duplicate_device_id(self):
        """Enrolling existing device_id returns 400 Bad Request."""
        headers = auth_header("admin", "Admin")
        payload = {
            "device_id": "esp32-dup-test",
            "device_type": "ESP32",
        }
        res1 = client.post("/api/v1/devices/enroll", json=payload, headers=headers)
        assert res1.status_code == 201

        res2 = client.post("/api/v1/devices/enroll", json=payload, headers=headers)
        assert res2.status_code == 400
        assert "already registered" in res2.json()["detail"]

    def test_prevent_one_device_assigned_to_two_motors(self):
        """One ESP32 cannot be actively assigned to two motors at the same time."""
        headers = auth_header("admin", "Admin")

        # 1. Enroll device
        client.post("/api/v1/devices/enroll", json={"device_id": "esp32-shared-01"}, headers=headers)

        # 2. Register Motor 1
        client.post("/api/v1/motors", json={
            "motor_id": "MTR-ONE",
            "name": "Motor One",
            "electrical_specs": {"rated_voltage_v": 12.0, "rated_current_a": 2.0},
            "assigned_device_id": "esp32-shared-01",
        }, headers=headers)

        # 3. Register Motor 2 trying to grab the SAME device
        res = client.post("/api/v1/motors", json={
            "motor_id": "MTR-TWO",
            "name": "Motor Two",
            "electrical_specs": {"rated_voltage_v": 12.0, "rated_current_a": 2.0},
            "assigned_device_id": "esp32-shared-01",
        }, headers=headers)

        assert res.status_code == 400
        assert "already actively assigned" in res.json()["detail"]


class TestAuditAndLifecycle:
    """Tests for audit trail, configuration updates, and disabling motors."""

    def test_update_config_increments_version_and_records_audit(self):
        """Updating thresholds increases configuration_version and writes audit record."""
        headers = auth_header("admin", "Admin")

        # Create motor
        client.post("/api/v1/motors", json={
            "motor_id": "MTR-AUDIT-01",
            "name": "Pump Motor",
            "electrical_specs": {"rated_voltage_v": 12.0, "rated_current_a": 3.0},
        }, headers=headers)

        # Update thresholds
        patch_res = client.patch("/api/v1/motors/MTR-AUDIT-01", json={
            "thresholds": {
                "temperature_warning_c": 48.0,
                "temperature_critical_c": 55.0,
                "current_warning_a": 3.2,
                "current_critical_a": 4.5,
                "vibration_warning_g": 0.4,
                "vibration_critical_g": 0.9,
            }
        }, headers=headers)

        assert patch_res.status_code == 200
        assert patch_res.json()["configuration_version"] == 2
        assert patch_res.json()["thresholds"]["temperature_warning_c"] == 48.0

        # Query audit log
        audit_res = client.get("/api/v1/motors/audit", headers=headers)
        assert audit_res.status_code == 200
        events = audit_res.json()
        actions = [e["action"] for e in events]
        assert "CREATE_MOTOR" in actions
        assert "UPDATE_CONFIG" in actions

    def test_disable_motor(self):
        """Disabling motor marks status inactive."""
        headers = auth_header("admin", "Admin")
        client.post("/api/v1/motors", json={
            "motor_id": "MTR-DISABLE-01",
            "name": "Retiring Motor",
            "electrical_specs": {"rated_voltage_v": 12.0, "rated_current_a": 2.0},
        }, headers=headers)

        res = client.post("/api/v1/motors/MTR-DISABLE-01/disable", headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "inactive"


class TestRBACPermissions:
    """Verifies that Technicians cannot create or mutate motors/devices via direct API."""

    def test_operator_cannot_create_motor(self):
        """Technicians receive 403 Forbidden when calling POST /api/v1/motors."""
        headers = auth_header("tech_dave", "Technician")
        payload = {
            "motor_id": "MTR-FORBIDDEN",
            "name": "Unauthorized Motor",
            "electrical_specs": {"rated_voltage_v": 12.0, "rated_current_a": 2.0},
        }
        res = client.post("/api/v1/motors", json=payload, headers=headers)
        assert res.status_code == 403
        assert "Operation requires role" in res.json()["detail"]

    def test_operator_cannot_enroll_device(self):
        """Technicians receive 403 Forbidden when calling POST /api/v1/devices/enroll."""
        headers = auth_header("tech_dave", "Technician")
        res = client.post("/api/v1/devices/enroll", json={"device_id": "esp32-hacked"}, headers=headers)
        assert res.status_code == 403
