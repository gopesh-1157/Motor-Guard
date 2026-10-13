"""
MotorGuard — MQTT Ingestion Integration Tests

Tests the end-to-end pipeline:
  MQTT subscriber → Pydantic validation → MongoDB deduplication → persistence

These tests use mongomock (via unittest mocks) to simulate MongoDB without
requiring a live MongoDB instance. They directly test the ingestion service
and the MQTT subscriber's message parsing logic.
"""

import uuid
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from pydantic import ValidationError

from backend.app.schemas.telemetry import TelemetryMessage
from backend.app.services.telemetry_ingestion import TelemetryIngestionService
from backend.app.mqtt.subscriber import MQTTSubscriber


# ---- Helpers ----------------------------------------------------------------

def make_valid_telemetry(
    device_id="ESP32-NODE-001",
    motor_id="MTR-775-001",
    source="hardware",
    seq=100,
    temp=34.2,
    current=1.45,
    vibration=0.42,
    event_id=None,
) -> dict:
    """Build a valid telemetry payload dict."""
    return {
        "schema_version": "1.0.0",
        "event_id": event_id or str(uuid.uuid4()),
        "device_id": device_id,
        "motor_id": motor_id,
        "source": source,
        "seq": seq,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "sensors": {
            "temperature_c": temp,
            "current_a": current,
            "vibration_g_rms": vibration,
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
            "probabilities": {"healthy": 0.96, "warning": 0.03, "critical": 0.01},
            "model_version": "1.0.1",
            "inference_time_ms": 7,
        },
        "diagnostics": {
            "wifi_rssi_dbm": -62,
            "free_heap_bytes": 184000,
            "uptime_seconds": 1040,
        },
    }


# ---- Schema Validation Tests ------------------------------------------------

class TestTelemetrySchemaValidation:
    """Test Pydantic schema validates/rejects payloads per telemetry contract."""

    def test_valid_payload_accepted(self):
        payload = make_valid_telemetry()
        msg = TelemetryMessage(**payload)
        assert msg.motor_id == "MTR-775-001"

    def test_simulator_source_accepted(self):
        payload = make_valid_telemetry(source="simulator", device_id="sim-node-001", motor_id="mtr-775-sim")
        msg = TelemetryMessage(**payload)
        assert msg.source == "simulator"

    def test_negative_current_rejected(self):
        payload = make_valid_telemetry(current=-0.5)
        with pytest.raises(ValidationError):
            TelemetryMessage(**payload)

    def test_out_of_range_temperature_rejected(self):
        payload = make_valid_telemetry(temp=150.0)  # Max is 120.0
        with pytest.raises(ValidationError):
            TelemetryMessage(**payload)

    def test_vibration_exceeding_max_rejected(self):
        payload = make_valid_telemetry(vibration=20.0)  # Max is 16.0
        with pytest.raises(ValidationError):
            TelemetryMessage(**payload)

    def test_null_sensor_with_disconnected_status(self):
        payload = make_valid_telemetry()
        payload["sensors"]["temperature_c"] = None
        payload["sensor_status"]["temperature"] = "DISCONNECTED"
        msg = TelemetryMessage(**payload)
        assert msg.sensors.temperature_c is None
        assert msg.sensor_status.temperature == "DISCONNECTED"

    def test_invalid_device_id_rejected(self):
        payload = make_valid_telemetry(device_id="a")  # min_length=3
        with pytest.raises(ValidationError):
            TelemetryMessage(**payload)

    def test_missing_required_field_rejected(self):
        payload = make_valid_telemetry()
        del payload["event_id"]
        with pytest.raises(ValidationError):
            TelemetryMessage(**payload)


# ---- Ingestion Service Tests ------------------------------------------------

class TestTelemetryIngestionService:
    """Test MongoDB ingestion with dedup behavior using mock collections."""

    @pytest.mark.asyncio
    async def test_successful_insert(self):
        """Valid payload is inserted into MongoDB collection."""
        mock_collection = AsyncMock()
        mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="abc123"))
        mock_collection.create_index = AsyncMock()

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = TelemetryIngestionService(mock_db)

        payload = make_valid_telemetry()
        validated = TelemetryMessage(**payload).model_dump()

        result = await service.ingest(validated)
        assert result is True
        mock_collection.insert_one.assert_called_once()
        # Verify server_received_at was added
        call_args = mock_collection.insert_one.call_args[0][0]
        assert "server_received_at" in call_args

    @pytest.mark.asyncio
    async def test_duplicate_safely_dropped(self):
        """Duplicate event_id is caught by DuplicateKeyError and returns False."""
        from pymongo.errors import DuplicateKeyError

        mock_collection = AsyncMock()
        mock_collection.insert_one = AsyncMock(
            side_effect=DuplicateKeyError("E11000 duplicate key error")
        )
        mock_collection.create_index = AsyncMock()

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = TelemetryIngestionService(mock_db)

        payload = make_valid_telemetry()
        validated = TelemetryMessage(**payload).model_dump()

        result = await service.ingest(validated)
        assert result is False  # Duplicate was safely dropped, no exception raised

    @pytest.mark.asyncio
    async def test_ensure_indexes_creates_three_indexes(self):
        """Verify ensure_indexes creates dedup, time-series, and TTL indexes."""
        mock_collection = AsyncMock()
        mock_collection.create_index = AsyncMock()

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        service = TelemetryIngestionService(mock_db)
        await service.ensure_indexes()

        assert mock_collection.create_index.call_count == 3


# ---- MQTT Subscriber Message Parsing Tests ----------------------------------

class TestMQTTSubscriberParsing:
    """Test MQTT on_message parsing and validation without a live broker."""

    def _make_mqtt_message(self, topic: str, payload_dict: dict) -> MagicMock:
        msg = MagicMock()
        msg.topic = topic
        msg.payload = json.dumps(payload_dict).encode("utf-8")
        return msg

    def test_valid_telemetry_message_increments_counter(self):
        subscriber = MQTTSubscriber()
        payload = make_valid_telemetry()
        msg = self._make_mqtt_message("motorguard/v1/ESP32-NODE-001/telemetry", payload)
        # Don't set a callback so we don't need an event loop
        subscriber._on_message(None, None, msg)
        assert subscriber._message_count == 1
        assert subscriber._error_count == 0

    def test_invalid_telemetry_increments_error_counter(self):
        subscriber = MQTTSubscriber()
        # Negative current will fail validation
        payload = make_valid_telemetry(current=-5.0)
        msg = self._make_mqtt_message("motorguard/v1/ESP32-NODE-001/telemetry", payload)
        subscriber._on_message(None, None, msg)
        assert subscriber._message_count == 0
        assert subscriber._error_count == 1

    def test_malformed_json_increments_error_counter(self):
        subscriber = MQTTSubscriber()
        msg = MagicMock()
        msg.topic = "motorguard/v1/ESP32-NODE-001/telemetry"
        msg.payload = b"not valid json{{"
        subscriber._on_message(None, None, msg)
        assert subscriber._error_count == 1

    def test_non_telemetry_topic_ignored(self):
        subscriber = MQTTSubscriber()
        msg = MagicMock()
        msg.topic = "motorguard/v1/ESP32-NODE-001/heartbeat"
        msg.payload = b'{"device_id":"test"}'
        subscriber._on_message(None, None, msg)
        assert subscriber._message_count == 0
        assert subscriber._error_count == 0
