"""
MotorGuard — Audit Remediation Verification Tests

Verifies remediation of confirmed findings from MotorGuard Readiness Audit:
  - MG-F05: Alert assignment role validation (reject non-technician, inactive, non-existent users).
  - MG-F04: MQTT topic device identity bound to payload device identity (reject mismatched spoofing).
  - MG-F03: Block automatic enrollment of unknown devices (quarantine as pending, reject telemetry).
  - MG-F08: Telemetry retention TTL index options verification.
"""

import json
import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.core.security import create_access_token
from backend.app.api.v1.endpoints.alerts import get_alert_service
from backend.app.services.alert_service import AlertService
from backend.app.mqtt.subscriber import MQTTSubscriber
from backend.app.services.device_service import DeviceService
from backend.app.services.telemetry_ingestion import TelemetryIngestionService


client = TestClient(app)


def auth_header(username: str, role: str) -> dict:
    token = create_access_token(data={"sub": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


def make_valid_telemetry(device_id="ESP32-NODE-001", motor_id="MTR-775-001"):
    return {
        "schema_version": "1.0.0",
        "event_id": str(uuid.uuid4()),
        "device_id": device_id,
        "motor_id": motor_id,
        "source": "hardware",
        "seq": 104,
        "timestamp": "2026-10-20T12:00:00.123Z",
        "sensors": {
            "temperature_c": 34.2,
            "current_a": 1.45,
            "vibration_g_rms": 0.42,
        },
        "sensor_status": {
            "temperature": "OK",
            "current": "OK",
            "vibration": "OK",
        },
        "inference": {
            "status": "PREDICTED",
            "health_status": "healthy",
            "confidence": 0.96,
            "probabilities": {
                "healthy": 0.96,
                "warning": 0.03,
                "critical": 0.01,
            },
            "model_version": "1.0.1",
            "inference_time_ms": 7,
        },
    }


class TestAlertAssignmentRoleValidation:
    """MG-F05: Alert assignment role validation."""

    def test_assign_alert_technician_success(self):
        """Manager assigning alert to verified Technician succeeds."""
        mock_alerts = AsyncMock()
        mock_users = AsyncMock()
        now = datetime.now(timezone.utc)

        # Mock technician user lookup
        mock_users.find_one = AsyncMock(return_value={
            "username": "tech_dave",
            "role": "Technician",
            "is_active": True,
        })
        mock_alerts.find_one_and_update = AsyncMock(return_value={
            "_id": "65f123456789abcdef012345",
            "alert_id": "ALT-ASSIGN-TEST-001",
            "motor_id": "MTR-TEST-001",
            "device_id": "esp32-node-001",
            "trigger_type": "THRESHOLD_OVERCURRENT",
            "trigger_value": 4.5,
            "threshold_limit": 4.0,
            "unit": "A",
            "severity": "CRITICAL",
            "state": "ACKNOWLEDGED",
            "message": "Overcurrent trip test",
            "triggered_at": now,
            "assigned_to": "tech_dave",
            "assigned_by": "manager_mike",
            "assigned_at": now,
            "priority": "URGENT",
            "instructions": "Inspect stator windings immediately",
        })

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: mock_alerts if name == "alerts" else mock_users)
        alert_service = AlertService(mock_db)

        app.dependency_overrides[get_alert_service] = lambda: alert_service
        try:
            headers = auth_header("manager_mike", "Manager")
            payload = {
                "technician_username": "tech_dave",
                "priority": "URGENT",
                "instructions": "Inspect stator windings immediately",
            }
            res = client.post("/api/v1/alerts/ALT-ASSIGN-TEST-001/assign", json=payload, headers=headers)
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["assigned_to"] == "tech_dave"
            assert data["state"] == "ACKNOWLEDGED"
        finally:
            app.dependency_overrides.pop(get_alert_service, None)

    def test_assign_alert_operator_rejected(self):
        """Manager assigning alert to Operator returns 400 Bad Request."""
        mock_alerts = AsyncMock()
        mock_users = AsyncMock()

        # Operator user lookup
        mock_users.find_one = AsyncMock(return_value={
            "username": "operator_bob",
            "role": "Operator",
            "is_active": True,
        })

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: mock_alerts if name == "alerts" else mock_users)
        alert_service = AlertService(mock_db)

        app.dependency_overrides[get_alert_service] = lambda: alert_service
        try:
            headers = auth_header("manager_mike", "Manager")
            payload = {
                "technician_username": "operator_bob",
                "priority": "HIGH",
            }
            res = client.post("/api/v1/alerts/ALT-ASSIGN-TEST-002/assign", json=payload, headers=headers)
            assert res.status_code == 400, res.text
            assert "requires technician or admin role" in res.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_alert_service, None)

    def test_assign_alert_nonexistent_user_rejected(self):
        """Manager assigning alert to non-existent user returns 404 Not Found."""
        mock_alerts = AsyncMock()
        mock_users = AsyncMock()

        # Non-existent user
        mock_users.find_one = AsyncMock(return_value=None)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: mock_alerts if name == "alerts" else mock_users)
        alert_service = AlertService(mock_db)

        app.dependency_overrides[get_alert_service] = lambda: alert_service
        try:
            headers = auth_header("manager_mike", "Manager")
            payload = {
                "technician_username": "ghost_technician_404",
                "priority": "HIGH",
            }
            res = client.post("/api/v1/alerts/ALT-ASSIGN-TEST-003/assign", json=payload, headers=headers)
            assert res.status_code == 404, res.text
            assert "not found" in res.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_alert_service, None)


class TestMQTTTopicIdentityBinding:
    """MG-F04: MQTT topic device identity bound to payload device identity."""

    def test_mqtt_topic_device_match_accepted(self):
        subscriber = MQTTSubscriber()
        payload = make_valid_telemetry(device_id="ESP32-NODE-001")
        msg = MagicMock()
        msg.topic = "motorguard/v1/ESP32-NODE-001/telemetry"
        msg.payload = json.dumps(payload).encode("utf-8")

        subscriber._on_message(None, None, msg)
        assert subscriber._message_count == 1
        assert subscriber._error_count == 0

    def test_mqtt_topic_device_mismatch_rejected(self):
        subscriber = MQTTSubscriber()
        payload = make_valid_telemetry(device_id="ESP32-SPOOFED-IDENTITY")
        msg = MagicMock()
        # Topic is ESP32-AUTHORIZED-001, but payload claims ESP32-SPOOFED-IDENTITY
        msg.topic = "motorguard/v1/ESP32-AUTHORIZED-001/telemetry"
        msg.payload = json.dumps(payload).encode("utf-8")

        subscriber._on_message(None, None, msg)
        assert subscriber._message_count == 0
        assert subscriber._error_count == 1


class TestDeviceAutoEnrollmentQuarantine:
    """MG-F03: Reject automatic enrollment of unknown devices; quarantine as pending."""

    @pytest.mark.asyncio
    async def test_unknown_device_quarantined_and_rejected(self):
        mock_devices = AsyncMock()
        mock_devices.find_one = AsyncMock(return_value=None)
        mock_devices.insert_one = AsyncMock()

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_devices)
        device_service = DeviceService(mock_db)

        unknown_id = f"ESP32-ROGUE-{uuid.uuid4().hex[:6]}"
        accepted = await device_service.record_heartbeat_or_telemetry(unknown_id, "MTR-775-001")
        assert accepted is False

        # Device should be inserted with pending quarantine
        mock_devices.insert_one.assert_called_once()
        inserted_doc = mock_devices.insert_one.call_args[0][0]
        assert inserted_doc["device_id"] == unknown_id
        assert inserted_doc["enrollment_status"] == "pending"
        assert inserted_doc["availability"] == "quarantined"
        assert inserted_doc["assigned_motor_id"] is None

    @pytest.mark.asyncio
    async def test_pending_quarantined_device_cannot_ingest_telemetry(self):
        mock_devices = AsyncMock()
        pending_id = f"ESP32-PENDING-{uuid.uuid4().hex[:6]}"
        mock_devices.find_one = AsyncMock(return_value={
            "device_id": pending_id,
            "enrollment_status": "pending",
            "availability": "quarantined",
            "assigned_motor_id": "MTR-775-001",
        })

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_devices)
        device_service = DeviceService(mock_db)

        accepted = await device_service.record_heartbeat_or_telemetry(pending_id, "MTR-775-001")
        assert accepted is False


    @pytest.mark.asyncio
    async def test_telemetry_ttl_index_migration_when_options_differ(self):
        """When idx_ttl_retention exists with an obsolete TTL, ensure_indexes drops and recreates it."""
        mock_col = MagicMock()
        mock_col.create_index = AsyncMock()
        mock_col.drop_index = AsyncMock()
        mock_col.index_information = AsyncMock(return_value={
            "idx_ttl_retention": {"expireAfterSeconds": 3600, "key": [("server_received_at", 1)]}
        })
        mock_db = {"telemetry": mock_col}

        service = TelemetryIngestionService(mock_db)
        await service.ensure_indexes()

        # Obsolete index should be dropped
        mock_col.drop_index.assert_called_once_with("idx_ttl_retention")

        # New index created with configured retention
        expected_seconds = int(settings.TELEMETRY_RETENTION_DAYS * 86400)
        ttl_calls = [
            call for call in mock_col.create_index.call_args_list
            if call.kwargs.get("name") == "idx_ttl_retention"
        ]
        assert len(ttl_calls) == 1
        assert ttl_calls[0].kwargs.get("expireAfterSeconds") == expected_seconds


class TestTelemetryIngestionDeviceValidation:
    """MG-F03/Phase 3: Telemetry ingestion drops packets from unauthorized devices."""

    @pytest.mark.asyncio
    async def test_unauthorized_device_drops_telemetry_before_db_insert(self):
        from unittest.mock import patch
        from backend.app.main import _ingest_and_broadcast

        mock_ingestion = MagicMock()
        mock_ingestion.ingest = AsyncMock(return_value=True)
        mock_ingestion._is_liveness_eligible = MagicMock(return_value=True)

        mock_device_service = MagicMock()
        # Device service rejects unauthorized/quarantined device
        mock_device_service.record_heartbeat_or_telemetry = AsyncMock(return_value=False)

        payload = make_valid_telemetry(device_id="ESP32-UNREGISTERED-ROGUE", motor_id="MTR-775-001")

        with patch("backend.app.main.ingestion_service", mock_ingestion), \
             patch("backend.app.main.device_service", mock_device_service):

            result = await _ingest_and_broadcast(payload)
            assert result is False

            # Ingestion must NOT be performed
            mock_ingestion.ingest.assert_not_called()

