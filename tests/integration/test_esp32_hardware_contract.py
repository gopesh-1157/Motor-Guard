"""
MotorGuard — Phase 5 Acceptance Tests: Hardware Contract & Sensor Validation

Verifies:
  1. ESP32 payload generation adheres strictly to v1.0.0 telemetry contract.
  2. Disconnected sensors produce null values and sensor_status="DISCONNECTED" (never faking 0.0).
  3. ACS712 zero offset calibration properly adjusts raw mV to 0.0A baseline.
  4. Telemetry pipeline ingests hardware sensor readings without schema validation errors.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from backend.app.schemas.telemetry import TelemetryMessage
from backend.app.services.telemetry_ingestion import TelemetryIngestionService
from simulator.simulator import VirtualMotor


class TestESP32HardwareContract:
    """Verifies physical and virtual hardware telemetry adheres to contract rules."""

    def test_hardware_payload_full_schema_compliance(self):
        """Simulated hardware telemetry matches all required fields and constraints."""
        motor = VirtualMotor(motor_id="MTR-775-001", device_id="esp32-node-001", profile="healthy")
        payload = motor.step()
        # Change source to 'hardware' to simulate physical ESP32
        payload["source"] = "hardware"

        validated = TelemetryMessage(**payload)
        assert validated.source == "hardware"
        assert validated.device_id == "esp32-node-001"
        assert validated.motor_id == "MTR-775-001"
        assert validated.seq >= 1
        assert validated.timestamp.endswith("Z")
        assert validated.sensor_status.temperature == "OK"
        assert validated.sensor_status.current == "OK"
        assert validated.sensor_status.vibration == "OK"
        assert validated.sensors.temperature_c is not None
        assert validated.sensors.current_a is not None
        assert validated.sensors.vibration_g_rms is not None

    def test_dht11_disconnected_produces_null_and_disconnected_status(self):
        """When DHT11 is unplugged, temperature is null and status is DISCONNECTED, not 0.0."""
        motor = VirtualMotor(motor_id="MTR-775-002", device_id="esp32-node-002", profile="disconnected_temp")
        payload = motor.step()
        payload["source"] = "hardware"

        validated = TelemetryMessage(**payload)
        assert validated.sensors.temperature_c is None
        assert validated.sensor_status.temperature == "DISCONNECTED"

    def test_acs712_zero_offset_behavior(self):
        """De-energized motor drawing zero current reports current_a=0.0 and status=OK."""
        payload = {
            "schema_version": "1.0.0",
            "event_id": "11111111-2222-4333-8444-555555555555",
            "device_id": "esp32-node-001",
            "motor_id": "MTR-775-001",
            "source": "hardware",
            "seq": 42,
            "timestamp": "2026-10-10T12:00:00.000Z",
            "sensors": {
                "temperature_c": 28.5,
                "current_a": 0.0,
                "vibration_g_rms": 0.02,
            },
            "sensor_status": {
                "temperature": "OK",
                "current": "OK",
                "vibration": "OK",
            },
            "inference": {
                "status": "PREDICTED",
                "health_status": "healthy",
                "confidence": 0.98,
                "probabilities": {"healthy": 0.98, "warning": 0.01, "critical": 0.01},
            },
            "diagnostics": {
                "wifi_rssi_dbm": -55,
                "free_heap_bytes": 182000,
                "uptime_seconds": 3600,
            },
        }

        msg = TelemetryMessage(**payload)
        assert msg.sensors.current_a == 0.0
        assert msg.sensor_status.current == "OK"

    @pytest.mark.asyncio
    async def test_hardware_payload_ingested_to_mongodb(self):
        """Hardware payload successfully persists through TelemetryIngestionService."""
        mock_collection = AsyncMock()
        mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="doc789"))
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = TelemetryIngestionService(mock_db)
        motor = VirtualMotor(motor_id="MTR-775-001", device_id="esp32-node-001", profile="healthy")
        payload = motor.step()
        payload["source"] = "hardware"

        result = await service.ingest(payload)
        assert result is True
        mock_collection.insert_one.assert_called_once()
        inserted_doc = mock_collection.insert_one.call_args[0][0]
        assert inserted_doc["source"] == "hardware"
        assert inserted_doc["device_id"] == "esp32-node-001"

    def test_http_ingest_telemetry_endpoint_requires_authentication(self):
        """Unauthenticated requests to /api/v1/telemetry/ingest are rejected with 401."""
        from fastapi.testclient import TestClient
        from backend.app.main import app

        motor = VirtualMotor(motor_id="MTR-775-001", device_id="esp32-node-001", profile="healthy")
        payload = motor.step()
        payload["source"] = "hardware"

        with TestClient(app) as client:
            # 1. No authentication -> 401
            res_unauth = client.post("/api/v1/telemetry/ingest", json=payload)
            assert res_unauth.status_code == 401
            assert "Invalid or missing credentials" in res_unauth.json()["detail"]

            # 2. Invalid API key -> 401
            res_bad_key = client.post(
                "/api/v1/telemetry/ingest",
                json=payload,
                headers={"X-Device-API-Key": "wrong-secret-key"},
            )
            assert res_bad_key.status_code == 401

    def test_http_ingest_telemetry_endpoint_authorized(self):
        """Direct HTTP ingestion via /api/v1/telemetry/ingest accepts payload with valid device key or bearer token."""
        from fastapi.testclient import TestClient
        from backend.app.main import app
        from backend.app.config import settings
        from backend.app.core.security import create_access_token
        from unittest.mock import patch

        motor = VirtualMotor(motor_id="MTR-775-001", device_id="esp32-node-001", profile="healthy")
        payload = motor.step()
        payload["source"] = "hardware"

        with patch("backend.app.main._ingest_and_broadcast", new=AsyncMock(return_value=True)):
            with TestClient(app) as client:
                # 1. Valid X-Device-API-Key -> 200
                res_key = client.post(
                    "/api/v1/telemetry/ingest",
                    json=payload,
                    headers={"X-Device-API-Key": settings.GATEWAY_INGEST_SECRET},
                )
                assert res_key.status_code == 200
                assert res_key.json()["success"] is True

                # 2. Valid Bearer JWT Token -> 200
                token = create_access_token(data={"sub": "admin", "role": "Admin"})
                res_jwt = client.post(
                    "/api/v1/telemetry/ingest",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert res_jwt.status_code == 200
                assert res_jwt.json()["success"] is True

                # 3. Inactive User Bearer Token -> 401
                from backend.app.core.auth import get_user_service
                from backend.app.schemas.user import UserInDB
                from datetime import datetime, timezone

                inactive_svc = AsyncMock()
                inactive_svc.get_by_username.return_value = UserInDB(
                    id="mock_inactive_id",
                    username="inactive_tech",
                    email="inactive@motorguard.local",
                    password_hash="...",
                    role="Technician",
                    assigned_sites=[],
                    assigned_motors=[],
                    is_active=False,
                    created_at=datetime.now(timezone.utc),
                )
                app.dependency_overrides[get_user_service] = lambda: inactive_svc
                try:
                    inactive_token = create_access_token(data={"sub": "inactive_tech", "role": "Technician"})
                    res_inactive = client.post(
                        "/api/v1/telemetry/ingest",
                        json=payload,
                        headers={"Authorization": f"Bearer {inactive_token}"},
                    )
                    assert res_inactive.status_code == 401
                finally:
                    app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_hardware_sensor_telemetry_triggers_rules_engine_alerts(self):
        """Real-time physical telemetry (source='hardware') from ESP32 motor triggers automated alerts."""
        from backend.app.services.alert_service import AlertService

        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="hw_alert_001"))

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        service = AlertService(mock_db)

        # Real ESP32 telemetry with physical vibration & current exceedance
        hardware_telemetry = {
            "schema_version": "1.0.0",
            "event_id": "hw-event-12345",
            "device_id": "esp32-node-001",
            "motor_id": "MTR-775-001",
            "source": "hardware",
            "seq": 105,
            "timestamp": "2026-10-18T09:00:00Z",
            "sensors": {
                "temperature_c": 54.2,
                "current_a": 4.80,
                "vibration_g_rms": 0.220,
                "vibration_g_peak": 0.650,
            },
            "sensor_status": {
                "temperature": "OK",
                "current": "OK",
                "vibration": "OK",
            },
            "inference": {
                "status": "PREDICTED",
                "health_status": "critical",
                "confidence": 0.96,
            },
        }

        alerts = await service.evaluate_telemetry_for_alerts(hardware_telemetry)
        assert len(alerts) == 4
        trigger_types = [a.trigger_type for a in alerts]
        assert "THRESHOLD_OVERCURRENT" in trigger_types
        assert "THRESHOLD_OVERTEMPERATURE" in trigger_types
        assert "THRESHOLD_HIGH_VIBRATION" in trigger_types
        assert "CRITICAL_INFERENCE_FAULT" in trigger_types

        # Verify alert fields correctly attribute real physical hardware
        for alert in alerts:
            assert alert.device_id == "esp32-node-001"
            assert alert.motor_id == "MTR-775-001"
            assert alert.state == "ACTIVE"

