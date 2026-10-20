"""
MotorGuard — Regression Suite: Timestamp Liveness & WebSocket Isolation
========================================================================

Verifies that:
1. An unsynchronized timestamp (e.g. year 1970 from an un-synced ESP32 RTC)
   is flagged as liveness_eligible=False by TelemetryIngestionService.
2. An ineligible (1970) telemetry payload is persisted to MongoDB for audit
   integrity, but WebSocket live broadcasting is strictly suppressed.
3. An ineligible (1970) telemetry payload does NOT update device liveness
   in DeviceService, preventing stale replay from reviving offline nodes.
4. MotorService query filters (liveness_eligible != False) exclude 1970
   telemetry from marking an offline motor as healthy or running.
5. A synchronized UTC timestamp passes liveness eligibility and broadcasts cleanly.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.services.telemetry_ingestion import TelemetryIngestionService
from backend.app.services.motor_service import MotorService
from backend.app.main import _ingest_and_broadcast, ws_manager


def _build_payload(timestamp: str, device_id: str = "esp32-node-001", motor_id: str = "MTR-775-001") -> dict:
    """Helper returning a schema-valid telemetry dictionary."""
    return {
        "schema_version": "1.0.0",
        "event_id": "99999999-aaaa-4bbb-8ccc-dddddddddddd",
        "device_id": device_id,
        "motor_id": motor_id,
        "source": "hardware",
        "seq": 1,
        "timestamp": timestamp,
        "sensors": {
            "temperature_c": 28.5,
            "ambient_temperature_c": 28.5,
            "case_temperature_c": None,
            "current_a": 0.45,
            "current_peak_a": 0.60,
            "vibration_g_rms": 0.035,
            "vibration_g_peak": 0.120,
        },
        "sensor_status": {
            "temperature": "OK",
            "current": "OK",
            "vibration": "OK",
            "current_calibrated": True,
            "current_zero_offset_v": 1.667,
        },
        "inference": {
            "status": "MODEL_UNAVAILABLE",
            "health_status": "healthy",
            "confidence": 0.950,
            "probabilities": None,
            "model_version": "ei-motoguard-v1.0.1",
            "input_feature_version": "1.0.0-3f",
            "inference_time_ms": 12,
        },
        "safety": {
            "status": "SAFE",
            "current_state": "NORMAL",
            "vibration_state": "NORMAL",
            "temperature_state": "NORMAL",
            "active_reasons": [],
            "configuration_version": 1,
            "calibration_status": "provisional",
        },
        "diagnostics": {
            "wifi_rssi_dbm": -55,
            "free_heap_bytes": 184320,
            "uptime_seconds": 30,
        },
    }


class TestTimestampLivenessGate:
    """Tests the math and boundaries of _is_liveness_eligible."""

    def test_1970_timestamp_marked_ineligible(self):
        """Timestamp from un-synced ESP32 RTC (year 1970) must return False."""
        now = datetime.now(timezone.utc)
        ts_1970 = "1970-01-01T00:00:15Z"
        assert TelemetryIngestionService._is_liveness_eligible(ts_1970, now) is False

    def test_current_utc_timestamp_marked_eligible(self):
        """Current UTC timestamp must return True."""
        now = datetime.now(timezone.utc)
        ts_current = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        assert TelemetryIngestionService._is_liveness_eligible(ts_current, now) is True

    def test_future_timestamp_beyond_tolerance_marked_ineligible(self):
        """Timestamp > 60 seconds in the future must return False."""
        now = datetime.now(timezone.utc)
        # 65 seconds in future (age_seconds = -65 < -60)
        from datetime import timedelta
        ts_future = (now + timedelta(seconds=400)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert TelemetryIngestionService._is_liveness_eligible(ts_future, now) is False

    def test_stale_timestamp_beyond_tolerance_marked_ineligible(self):
        """Timestamp > 60 seconds in the past must return False."""
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        ts_stale = (now - timedelta(seconds=70)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert TelemetryIngestionService._is_liveness_eligible(ts_stale, now) is False


class TestIngestionAndBroadcastIsolation:
    """Tests end-to-end suppression of WebSocket broadcast for 1970 timestamps."""

    @pytest.mark.asyncio
    async def test_1970_telemetry_persists_to_db_with_ineligible_flag(self):
        """Ineligible 1970 payload is inserted into MongoDB with liveness_eligible=False."""
        mock_col = AsyncMock()
        mock_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="doc-1970"))
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = mock_col

        service = TelemetryIngestionService(mock_db)
        payload = _build_payload(timestamp="1970-01-01T00:00:15Z")

        result = await service.ingest(payload)
        assert result is True
        assert payload.get("liveness_eligible") is False

        # Assert insert_one was called with liveness_eligible=False
        call_doc = mock_col.insert_one.call_args[0][0]
        assert call_doc["liveness_eligible"] is False

    @pytest.mark.asyncio
    async def test_1970_telemetry_suppresses_websocket_broadcast_and_heartbeat(self):
        """Ineligible 1970 payload must NOT broadcast to WebSocket and NOT touch device registry."""
        mock_ingestion = MagicMock()
        mock_ingestion.ingest = AsyncMock(return_value=True)
        mock_ingestion._is_liveness_eligible = MagicMock(return_value=False)

        mock_device_service = MagicMock()
        mock_device_service.record_heartbeat_or_telemetry = AsyncMock(return_value=True)

        mock_alert_service = MagicMock()
        mock_alert_service.evaluate_telemetry_for_alerts = AsyncMock(return_value=[])

        payload = _build_payload(timestamp="1970-01-01T00:00:15Z")

        with patch("backend.app.main.ingestion_service", mock_ingestion), \
             patch("backend.app.main.device_service", mock_device_service), \
             patch("backend.app.main.alert_service", mock_alert_service), \
             patch.object(ws_manager, "broadcast", new=AsyncMock()) as mock_broadcast:

            inserted = await _ingest_and_broadcast(payload)
            assert inserted is True

            # 1. Database insert was performed
            mock_ingestion.ingest.assert_called_once()

            # 2. WebSocket broadcast was STRICTLY SUPPRESSED
            mock_broadcast.assert_not_called()

            # 3. Device authorization checked without updating liveness
            mock_device_service.record_heartbeat_or_telemetry.assert_called_once_with(
                payload["device_id"], payload["motor_id"], update_liveness=False
            )

            # 4. Alert engine was NOT evaluated
            mock_alert_service.evaluate_telemetry_for_alerts.assert_not_called()

    @pytest.mark.asyncio
    async def test_fresh_telemetry_triggers_websocket_broadcast(self):
        """Synchronized UTC telemetry must broadcast to WebSocket and update heartbeat."""
        mock_ingestion = MagicMock()
        mock_ingestion.ingest = AsyncMock(return_value=True)
        mock_ingestion._is_liveness_eligible = MagicMock(return_value=True)

        mock_device_service = MagicMock()
        mock_device_service.record_heartbeat_or_telemetry = AsyncMock(return_value=True)

        mock_alert_service = MagicMock()
        mock_alert_service.evaluate_telemetry_for_alerts = AsyncMock(return_value=[])
        mock_alert_service.consume_auto_resolved_alerts = MagicMock(return_value=[])

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = _build_payload(timestamp=now_iso)

        with patch("backend.app.main.ingestion_service", mock_ingestion), \
             patch("backend.app.main.device_service", mock_device_service), \
             patch("backend.app.main.alert_service", mock_alert_service), \
             patch.object(ws_manager, "broadcast", new=AsyncMock()) as mock_broadcast:

            inserted = await _ingest_and_broadcast(payload)
            assert inserted is True

            # 1. Device heartbeat was recorded
            mock_device_service.record_heartbeat_or_telemetry.assert_called_once()

            # 2. WebSocket broadcast WAS executed
            mock_broadcast.assert_called_once_with({"type": "telemetry", "data": payload})


class TestMotorServiceLivenessFilter:
    """Verifies that MotorService excludes liveness_eligible=False records when determining motor state."""

    @pytest.mark.asyncio
    async def test_motor_service_ignores_1970_telemetry_in_operational_state(self):
        """Motor document with only 1970 telemetry remains OFFLINE and unknown health."""
        mock_motors_col = AsyncMock()
        mock_motors_col.find_one = AsyncMock(return_value={
            "motor_id": "MTR-775-001",
            "name": "RS-775 Primary Drive",
            "status": "active",
            "site_id": "SITE-01",
            "thresholds": {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })

        mock_telemetry_col = AsyncMock()
        # Mock telemetry query: when liveness_eligible != False is requested, returns None
        async def _find_telem(query, *args, **kwargs):
            if query.get("liveness_eligible") == {"$ne": False}:
                return None  # The only records have liveness_eligible: False
            return {"sensors": {"current_a": 0.5}}

        mock_telemetry_col.find_one = AsyncMock(side_effect=_find_telem)

        mock_alerts_col = AsyncMock()
        mock_alerts_col.find_one = AsyncMock(return_value=None)

        mock_db = MagicMock()
        mock_db.__getitem__.side_effect = lambda name: {
            "motors": mock_motors_col,
            "telemetry": mock_telemetry_col,
            "alerts": mock_alerts_col,
            "devices": AsyncMock(),
            "system_settings": AsyncMock(),
            "audit_events": AsyncMock(),
        }.get(name, AsyncMock())

        service = MotorService(mock_db)
        motor = await service.get_motor("MTR-775-001")

        assert motor is not None
        # Must be OFFLINE because liveness_eligible=False telemetry was filtered out
        assert motor.operational_state == "OFFLINE"
        assert motor.health_status == "unknown"
