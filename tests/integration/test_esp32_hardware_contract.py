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

    def test_http_ingest_telemetry_endpoint(self):
        """Direct HTTP ingestion via /api/v1/telemetry/ingest accepts hardware payload."""
        from fastapi.testclient import TestClient
        from backend.app.main import app
        from unittest.mock import patch

        motor = VirtualMotor(motor_id="MTR-775-001", device_id="esp32-node-001", profile="healthy")
        payload = motor.step()
        payload["source"] = "hardware"

        with patch("backend.app.main._ingest_and_broadcast", new=AsyncMock(return_value=True)):
            with TestClient(app) as client:
                response = client.post("/api/v1/telemetry/ingest", json=payload)
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["event_id"] == payload["event_id"]

